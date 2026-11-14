"use client";

import Link from "next/link";
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";

import { TabGlyph } from "@/components/TabGlyph";
import {
  activeBottomTab,
  bottomTabAriaLabel,
  bottomTabBadgeText,
  normalizePillContext,
  pillActiveIndex,
  pillMode,
  pillPrimaryCompact,
  pillScrollTarget,
  pillTabText,
  PILL_MENU_LABEL,
  type BottomTab,
  type PillContext,
} from "@/lib/bottomNav";

import "./ui.css";

/**
 * Phone bottom pill (approved: option B + the V2 "smart pill", docs/audits/2026-11-smart-pill-options.html).
 * A floating glass capsule, 12px off the edges and above the home-indicator inset.
 *
 * - No page context: the global tabs. The lit tab expands to icon + label in a cyan capsule, the rest are icon-only
 *   (aria-label names them), 44px+ targets, a count badge.
 * - With a page `context` (useBottomPillContext): ONE row. The global tabs fold into two icon buttons (the section you
 *   are in + a menu button, aria-expanded) and the page segment (page tabs as a tablist, one primary chip) takes the
 *   rest. The menu button unfolds the full global row in the same pill; picking a tab (or Escape / tapping outside)
 *   folds it back. The lit page tab is one capsule that slides between tabs.
 *
 * Meant to live inside a `.bottom-stack` (sticky, in flow), never position:fixed; both layers share one grid cell so
 * the pill is one row tall in every mode (clearance = the stack height). Hidden from 768px up. Motion is opacity and
 * transform only, from lib/motion.ts tokens (CSS vars), crossfade only under reduced motion.
 * Mobile twin: mobile/src/components/BottomPill.tsx.
 */
export function BottomTabBar({
  tabs,
  active,
  onSelect,
  ariaLabel,
  testId = "bottom-tab-bar",
  context: rawContext,
}: {
  tabs: BottomTab[];
  active: string;
  onSelect?: (key: string) => void;
  ariaLabel: string;
  testId?: string;
  context?: PillContext | null;
}) {
  const current = activeBottomTab(tabs, active);
  const context = normalizePillContext(rawContext);
  const contextId = context?.id ?? null;
  // The menu folds on its own when the page (context id) changes: state is tagged with the id it was opened for.
  const [menuState, setMenuState] = useState<{ id: string | null; open: boolean }>({ id: null, open: false });
  const menuOpen = menuState.open && menuState.id === contextId;
  const setMenuOpen = useCallback((v: boolean | ((o: boolean) => boolean)) => setMenuState((s) => ({ id: contextId, open: typeof v === "function" ? v(s.open && s.id === contextId) : v })), [contextId]);
  const mode = pillMode(Boolean(context), menuOpen);
  const navRef = useRef<HTMLElement>(null);
  const menuBtnRef = useRef<HTMLButtonElement>(null);
  const globalRef = useRef<HTMLUListElement>(null);
  const wasOpen = useRef(false);

  const closeMenu = useCallback((refocus: boolean) => {
    setMenuOpen(false);
    if (refocus) requestAnimationFrame(() => menuBtnRef.current?.focus());
  }, [setMenuOpen]);

  // Focus: opening moves focus to the lit global tab, closing by keyboard returns it to the menu button.
  useEffect(() => {
    if (menuOpen) {
      wasOpen.current = true;
      globalRef.current?.querySelector<HTMLElement>('[aria-current="page"], .bottom-tab')?.focus();
    }
  }, [menuOpen]);

  useEffect(() => {
    if (!menuOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") closeMenu(true);
    };
    const onDown = (e: PointerEvent) => {
      if (navRef.current && !navRef.current.contains(e.target as Node)) closeMenu(false);
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("pointerdown", onDown);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("pointerdown", onDown);
    };
  }, [menuOpen, closeMenu]);

  const activeTab = tabs.find((t) => t.key === current) ?? tabs[0];

  return (
    <nav
      ref={navRef}
      className="bottom-tab-bar"
      aria-label={ariaLabel}
      data-testid={testId}
      data-mode={mode}
      data-has-context={context ? "" : undefined}
    >
      <div className="pill-layer pill-layer--global" inert={mode === "context"} data-testid="pill-global-layer">
        <ul ref={globalRef}>
          {tabs.map((tab, i) => {
            const badge = bottomTabBadgeText(tab.badge);
            const body = (
              <>
                <span className="bottom-tab-icon" aria-hidden="true">
                  <TabGlyph name={tab.glyph} size={22} />
                </span>
                <span className="bottom-tab-label">{tab.label}</span>
                {badge ? (
                  <span className="bottom-tab-badge" aria-hidden="true" data-testid={`bottom-tab-badge-${tab.key}`}>
                    {badge}
                  </span>
                ) : null}
              </>
            );
            const pick = () => {
              onSelect?.(tab.key);
              if (menuOpen) closeMenu(false);
            };
            const common = {
              className: "bottom-tab",
              "aria-current": tab.key === current ? ("page" as const) : undefined,
              "aria-label": bottomTabAriaLabel(tab),
              "data-tab": tab.key,
            };
            return (
              <li key={tab.key} data-active={tab.key === current ? "" : undefined} style={{ "--i": i } as React.CSSProperties}>
                {tab.href ? (
                  <Link href={tab.href} {...common} onClick={pick}>
                    {body}
                  </Link>
                ) : (
                  <button type="button" {...common} onClick={pick}>
                    {body}
                  </button>
                )}
              </li>
            );
          })}
        </ul>
      </div>
      {context ? (
        <PillContextLayer
          key={context.id}
          context={context}
          hidden={mode === "menu"}
          section={activeTab}
          menuOpen={menuOpen}
          menuBtnRef={menuBtnRef}
          onMenu={() => setMenuOpen((o) => !o)}
          onSection={() => activeTab && onSelect?.(activeTab.key)}
        />
      ) : null}
    </nav>
  );
}

export function PillContextLayer({
  context,
  hidden,
  section,
  menuOpen,
  menuBtnRef,
  onMenu,
  onSection,
  noMenu,
}: {
  context: PillContext;
  hidden: boolean;
  /** The section icon (site shell). Omitted in the Fantasy Sim bar, where the orb is the navigator. */
  section?: BottomTab | undefined;
  menuOpen: boolean;
  menuBtnRef: React.RefObject<HTMLButtonElement | null>;
  onMenu: () => void;
  onSection?: () => void;
  /** No menu button (a context with no row to unfold back to). */
  noMenu?: boolean;
}) {
  const listRef = useRef<HTMLDivElement>(null);
  const idx = pillActiveIndex(context);
  // The entrance animation (CSS, on mount) replays per page because the layer is keyed by the context id; folding and
  // unfolding the menu never remounts it, so those are transition-only.

  // The lit capsule is one element that slides: measure the lit tab, move by transform/width (no layout of siblings).
  // The strip scrolls (never clips a label): the lit tab is brought fully into view, clear of the edge fades.
  const [segW, setSegW] = useState(0);
  const layerRef = useRef<HTMLDivElement>(null);
  useLayoutEffect(() => {
    const list = listRef.current;
    const el = list?.querySelectorAll<HTMLElement>('[role="tab"]')[idx];
    if (!list || !el) return;
    list.style.setProperty("--ind-x", `${el.offsetLeft}px`);
    list.style.setProperty("--ind-w", `${el.offsetWidth}px`);
    list.dataset.measured = "";
    const to = pillScrollTarget(el.offsetLeft, el.offsetWidth, list.clientWidth, list.scrollLeft, list.scrollWidth);
    if (Math.abs(to - list.scrollLeft) > 1) list.scrollTo?.({ left: to });
  }, [idx, context.tabs, segW]);
  // Fade only the edge that has more tabs behind it; the primary chip's form follows the width the segment really has.
  useLayoutEffect(() => {
    const list = listRef.current;
    const layer = layerRef.current;
    if (!list || !layer) return;
    const update = () => {
      const more = list.scrollWidth > list.clientWidth + 1;
      const start = more && list.scrollLeft > 1;
      const end = more && list.scrollLeft + list.clientWidth < list.scrollWidth - 1;
      list.dataset.fade = start && end ? "both" : start ? "start" : end ? "end" : "";
      const taken = [...layer.children].reduce((n, k) => (k === list || (k as HTMLElement).classList.contains("pill-primary") ? n : n + (k as HTMLElement).offsetWidth), 0);
      setSegW(Math.max(0, layer.clientWidth - taken - 8));
    };
    update();
    list.addEventListener("scroll", update, { passive: true });
    if (typeof ResizeObserver === "undefined") return () => list.removeEventListener("scroll", update);
    const ro = new ResizeObserver(update);
    ro.observe(layer);
    ro.observe(list);
    return () => {
      list.removeEventListener("scroll", update);
      ro.disconnect();
    };
  }, [context.tabs]);

  const primary = context.primary;
  const sectionBody = section ? <TabGlyph name={section.glyph} size={22} /> : null;
  const sectionProps = { className: "pill-icon-btn pill-icon-btn--section", "aria-label": section?.label ?? "Section", "data-testid": "pill-section" };
  return (
    <div ref={layerRef} className="pill-layer pill-layer--context" inert={hidden} data-testid="pill-context-layer">
      {!section ? null : section.href ? (
        <Link href={section.href} {...sectionProps} onClick={() => onSection?.()}>
          {sectionBody}
        </Link>
      ) : (
        <button type="button" {...sectionProps} onClick={() => onSection?.()}>
          {sectionBody}
        </button>
      )}
      {noMenu ? null : <button
        ref={menuBtnRef}
        type="button"
        className="pill-icon-btn pill-icon-btn--menu"
        aria-label={PILL_MENU_LABEL}
        aria-expanded={menuOpen}
        data-testid="pill-menu"
        onClick={onMenu}
      >
        <TabGlyph name="more" size={22} />
      </button>}
      <span className="pill-divider" aria-hidden="true" />
      <div ref={listRef} role="tablist" aria-label={context.label} className="pill-tabs" data-dense={context.tabs.length >= 4 ? "" : undefined} data-testid="pill-tabs">
        {idx >= 0 ? <span className="pill-indicator" aria-hidden="true" /> : null}
        {context.tabs.map((t) => {
          const on = t.key === context.activeKey;
          const badge = bottomTabBadgeText(t.badge);
          return (
            <PillTabEl
              key={t.key}
              href={t.href}
              className="pill-tab"
              role="tab"
              aria-selected={on}
              tabIndex={on ? 0 : -1}
              data-tab={t.key}
              aria-label={t.short ? t.label : undefined}
              onClick={() => context.onSelect(t.key)}
              onKeyDown={(e: React.KeyboardEvent) => {
                const dir = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
                if (!dir) return;
                const next = context.tabs[(idx + dir + context.tabs.length) % context.tabs.length];
                if (!next) return;
                e.preventDefault();
                context.onSelect(next.key);
                requestAnimationFrame(() => listRef.current?.querySelector<HTMLElement>(`[data-tab="${next.key}"]`)?.focus());
              }}
            >
              <span className="pill-tab-text">{pillTabText(t)}</span>
              {badge ? <span className="pill-tab-badge" aria-label={`${badge} new`}>{badge}</span> : null}
            </PillTabEl>
          );
        })}
      </div>
      {primary ? (
        <PillTabEl
          key={`${context.id}:${primary.key}`}
          href={primary.disabled || primary.busy ? undefined : primary.href}
          className="pill-primary"
          data-compact={pillPrimaryCompact(context, segW) ? "" : undefined}
          aria-label={primary.label}
          disabled={primary.disabled || primary.busy}
          aria-busy={primary.busy || undefined}
          data-testid="pill-primary"
          onClick={primary.onPress}
        >
          {primary.glyph ? <TabGlyph name={primary.glyph} size={16} /> : null}
          <span className="pill-primary-label">{primary.label}</span>
        </PillTabEl>
      ) : null}
    </div>
  );
}

/** A pill control: a client-navigation link when it has an href (a route), otherwise a button. */
function PillTabEl({ href, children, ...rest }: { href?: string; children: React.ReactNode } & Record<string, unknown>) {
  if (href) return <Link href={href} {...(rest as Record<string, unknown>)}>{children}</Link>;
  return (
    <button type="button" {...(rest as Record<string, unknown>)}>
      {children}
    </button>
  );
}
