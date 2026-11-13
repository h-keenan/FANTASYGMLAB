"use client";

import { PulseOnIncrease } from "@/components/Motion";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState, type KeyboardEvent, type ReactNode } from "react";

import type { TabIconName } from "@/lib/tabIcons";

import { TabGlyph } from "./TabGlyph";

/**
 * The one segmented control / tab bar. Every tab strip in the app is this
 * component; sizing comes from the `--segmented-*` tokens in globals.css.
 *
 * Variants:
 *  - "fill"    equal-width segments across the full row (primary tabs).
 *  - "compact" segments hug their content, no empty bordered area (year /
 *              short toggles). Default.
 *  - "scroll"  full-width single-row strip that scrolls horizontally with
 *              edge fades, never wraps (many / long labels, e.g. filters).
 * Any variant falls back to horizontal scrolling instead of wrapping when
 * its labels overflow. `fullWidth` is kept as an alias for variant="fill".
 *
 * Icons: an option may carry `glyph` (a name from lib/tabIcons.ts, the
 * registry shared with mobile) or a raw `icon` node. With icons, phones stack
 * the glyph over the label (equal-width segments, so six tabs fit 390px with
 * no clipped last tab); from sm up they sit side by side. The active tab is
 * marked by a cyan glass pill plus a sliding underline (~180ms, off under
 * prefers-reduced-motion).
 *
 * Accessibility: role="tablist", role="tab" + aria-selected, roving tabindex,
 * Arrow/Home/End keys move focus (and select, for button tabs). Options with
 * an `href` render as links so route tabs (Trades) use the same control.
 */
export type PillRowVariant = "fill" | "compact" | "scroll";

export function PillRow({
  options,
  active,
  onSelect,
  fullWidth = false,
  variant,
  ariaLabel,
  sticky = false,
  slim = false,
  tabIdPrefix,
  className: extraClass,
}: {
  /** `icon` is an optional glyph slot rendered before the label (tab icons are added in this one place). */
  options: { label: string; value: string; href?: string; icon?: ReactNode; glyph?: TabIconName; count?: number }[];
  active: string;
  onSelect?: (value: string) => void;
  fullWidth?: boolean;
  variant?: PillRowVariant;
  ariaLabel?: string;
  /** Pin the strip under the top of the viewport and use the compact height. For page-level tab bars. */
  sticky?: boolean;
  /**
   * The sleek in-sheet look (shared Tabs): no outer box, a hairline under the strip, the active tab marked by
   * its text weight and the sliding underline only. Same control, same keys and indicator; just quieter chrome.
   */
  slim?: boolean;
  /** Gives every tab an id and aria-controls (`${prefix}-tab-${value}` / `${prefix}-panel-${value}`) so a tabpanel can point back. */
  tabIdPrefix?: string;
  /** Extra classes on the root (e.g. `max-md:hidden` when a bottom bar replaces the strip on phones). */
  className?: string;
}) {
  const mode: PillRowVariant = variant ?? (fullWidth ? "fill" : "compact");
  const scrollerRef = useRef<HTMLDivElement>(null);
  const [fade, setFade] = useState({ left: false, right: false });
  const [indicator, setIndicator] = useState<{ left: number; width: number } | null>(null);
  const [animate, setAnimate] = useState(false);

  const measure = useCallback(() => {
    const el = scrollerRef.current;
    if (!el) return;
    const left = el.scrollLeft > 1;
    const right = el.scrollLeft + el.clientWidth < el.scrollWidth - 1;
    setFade((prev) => (prev.left === left && prev.right === right ? prev : { left, right }));
  }, []);

  // Keep the selected tab in view (scrolls only the strip, never the page).
  useEffect(() => {
    const el = scrollerRef.current;
    if (!el) return;
    const selected = el.querySelector<HTMLElement>('[aria-selected="true"]');
    if (selected && el.scrollWidth > el.clientWidth) {
      // Scroll the minimum needed so the selected tab is fully visible.
      const left = selected.offsetLeft;
      const right = left + selected.offsetWidth;
      if (left < el.scrollLeft) el.scrollLeft = left;
      else if (right > el.scrollLeft + el.clientWidth) el.scrollLeft = right - el.clientWidth;
    }
    measure();
  }, [active, options.length, measure]);

  // Sliding underline: track the selected tab's box inside the scroller.
  const placeIndicator = useCallback(() => {
    const el = scrollerRef.current;
    const selected = el?.querySelector<HTMLElement>('[aria-selected="true"]');
    if (!selected) {
      setIndicator(null);
      return;
    }
    const next = { left: selected.offsetLeft, width: selected.offsetWidth };
    setIndicator((prev) => (prev && prev.left === next.left && prev.width === next.width ? prev : next));
  }, []);

  useEffect(() => {
    placeIndicator();
    // Animate only moves after the first placement, never the initial paint.
    const frame = requestAnimationFrame(() => setAnimate(true));
    return () => cancelAnimationFrame(frame);
  }, [active, options.length, placeIndicator]);

  useEffect(() => {
    measure();
    if (typeof ResizeObserver === "undefined" || !scrollerRef.current) return;
    const observer = new ResizeObserver(() => {
      measure();
      placeIndicator();
    });
    observer.observe(scrollerRef.current);
    return () => observer.disconnect();
  }, [measure, placeIndicator]);

  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    const keys = ["ArrowLeft", "ArrowRight", "Home", "End"];
    if (!keys.includes(event.key)) return;
    const tabs = Array.from(scrollerRef.current?.querySelectorAll<HTMLElement>('[role="tab"]') ?? []);
    if (tabs.length === 0) return;
    const current = tabs.findIndex((tab) => tab === document.activeElement);
    let next = current < 0 ? 0 : current;
    if (event.key === "ArrowRight") next = (current + 1) % tabs.length;
    else if (event.key === "ArrowLeft") next = (current - 1 + tabs.length) % tabs.length;
    else if (event.key === "Home") next = 0;
    else next = tabs.length - 1;
    event.preventDefault();
    tabs[next].focus();
    const option = options[next];
    if (option && !option.href) onSelect?.(option.value);
  }

  const hasActive = options.some((option) => option.value === active);
  const mask = `linear-gradient(to right, ${fade.left ? "transparent 0, #000 var(--space-xl)" : "#000 0"}, ${
    fade.right ? "#000 calc(100% - var(--space-xl)), transparent 100%" : "#000 100%"
  })`;
  const anyIcon = options.some((option) => option.icon || option.glyph);
  // Five or more icon tabs in a fill row split the width equally (min-w-0) so they fit a phone.
  const equalFit = mode === "fill" && anyIcon && options.length >= 5;
  const segment =
    mode === "fill" ? (equalFit ? "flex-1 min-w-0" : "flex-1 min-w-fit") : "shrink-0 min-w-[var(--touch-target-min)]";

  return (
    <div
      className={`${mode === "compact" ? "flex max-w-full self-start" : "flex w-full"}${sticky ? " sticky z-20" : ""}${extraClass ? ` ${extraClass}` : ""}`}
      style={
        slim
          ? { borderBottom: "var(--border-width-default) solid var(--color-border)", background: "transparent", ...(sticky ? { top: 0 } : null) }
          : { border: "var(--border-width-default) solid var(--color-border)", background: "var(--color-surface-muted)", ...(sticky ? { top: 0 } : null) }
      }
    >
      <div
        ref={scrollerRef}
        role="tablist"
        aria-label={ariaLabel}
        onKeyDown={onKeyDown}
        onScroll={measure}
        className={`relative flex min-w-0 overflow-x-auto ${mode === "fill" ? "w-full" : ""}`}
        style={{
          gap: "var(--segmented-gap)",
          scrollbarWidth: "none",
          WebkitMaskImage: fade.left || fade.right ? mask : undefined,
          maskImage: fade.left || fade.right ? mask : undefined,
        }}
      >
        {options.map((option, index) => {
          const isActive = option.value === active;
          const tabbable = isActive || (!hasActive && index === 0);
          const hasIcon = Boolean(option.icon || option.glyph);
          const className = `${segment} relative flex items-center justify-center whitespace-nowrap text-center font-bold uppercase ${
            hasIcon ? "text-[length:var(--segmented-font-size-stacked)] sm:text-[length:var(--segmented-font-size)]" : "text-[length:var(--segmented-font-size)]"
          }`;
          const style = {
            // Icon tabs keep the full 44px touch target even in the sticky bar.
            minHeight: (sticky || slim) && !anyIcon ? "var(--segmented-height-compact)" : "var(--segmented-height)",
            padding: slim ? "0 var(--space-sm)" : equalFit ? "0 var(--space-xs)" : mode === "fill" ? "0 min(var(--segmented-padding-x), 0.5rem)" : "0 var(--segmented-padding-x)",
            letterSpacing: "var(--letter-spacing-tight)",
            background: isActive && !slim ? "var(--segmented-active-bg, var(--color-information-soft))" : "transparent",
            color: isActive ? "var(--segmented-active-fg, var(--color-text-primary))" : "var(--color-text-secondary)",
            // The sliding underline replaces the static one once measured.
            boxShadow: isActive && !indicator ? "inset 0 -2px 0 var(--color-information)" : "none",
            borderLeft: index === 0 || slim ? "none" : "var(--border-width-default) solid var(--color-border)",
          } as const;
          const common = {
            id: tabIdPrefix ? `${tabIdPrefix}-tab-${option.value}` : undefined,
            "aria-controls": tabIdPrefix ? `${tabIdPrefix}-panel-${option.value}` : undefined,
            role: "tab" as const,
            "aria-selected": isActive,
            tabIndex: tabbable ? 0 : -1,
            className,
            style,
          };
          const countPill = option.count ? (
            <span
              className={`inline-flex items-center justify-center text-[0.6875rem] font-extrabold leading-none${
                option.icon || option.glyph ? " absolute right-1 top-1 sm:static" : ""
              }`}
              style={{ minWidth: 16, height: 16, padding: "0 4px", borderRadius: "var(--radius-pill)", background: "var(--color-accent)", color: "var(--color-on-accent)" }}
              aria-label={`${option.count} new`}
            >
              <PulseOnIncrease value={option.count}>{option.count}</PulseOnIncrease>
            </span>
          ) : null;
          // Phones stack the icon over the label so six tabs fit; from sm up they sit side by side.
          const iconNode = option.icon ?? (option.glyph ? <TabGlyph name={option.glyph} /> : null);
          const content: ReactNode =
            iconNode || countPill ? (
              <span className="inline-flex min-w-0 flex-col items-center gap-0.5 sm:flex-row sm:gap-1.5">
                {iconNode ? (
                  <span
                    aria-hidden="true"
                    className="inline-flex"
                    style={{ color: isActive ? "var(--segmented-active-icon, var(--segmented-active-fg, var(--color-accent)))" : "var(--color-text-muted)" }}
                  >
                    {iconNode}
                  </span>
                ) : null}
                <span className="inline-flex min-w-0 items-center gap-1">
                  {option.label}
                  {countPill}
                </span>
              </span>
            ) : (
              option.label
            );
          if (option.href) {
            return (
              <Link key={option.value} href={option.href} {...common}>
                {content}
              </Link>
            );
          }
          return (
            <button key={option.value} type="button" onClick={() => onSelect?.(option.value)} {...common}>
              {content}
            </button>
          );
        })}
        {indicator ? (
          <span
            aria-hidden="true"
            className="tab-indicator"
            data-animate={animate ? "true" : "false"}
            style={{ width: indicator.width, transform: `translateX(${indicator.left}px)` }}
          />
        ) : null}
      </div>
    </div>
  );
}

/** Vertical stack for several tab/filter controls: one shared gap. */
export function TabStack({ children }: { children: ReactNode }) {
  return <div className="flex flex-col" style={{ gap: "var(--segmented-stack-gap)" }}>{children}</div>;
}
