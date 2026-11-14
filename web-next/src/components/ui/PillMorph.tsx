"use client";

import { useCallback, useRef, useState, type ReactNode } from "react";

import { TabGlyph } from "@/components/TabGlyph";
import { PillContextLayer } from "@/components/ui/BottomTabBar";
import { normalizePillContext, pillMode, PILL_MENU_LABEL, type PillContext } from "@/lib/bottomNav";

import "./ui.css";

/**
 * The smart pill's morph for the Fantasy Sim bar (the site shell's version is BottomTabBar). `children` is the bar's
 * normal row (Sim to | orb | Advance); with a page `context` the row folds into the page segment (page tabs + one primary)
 * and a menu button (aria-expanded) unfolds the row again. Without a context it renders `children` untouched
 * (`display: contents`), so desktop and pages that register nothing are exactly as before. Same CSS, motion and
 * reduced-motion rules as the shell pill (ui.css "Smart pill"). Mobile twin: mobile/src/components/BottomPill.tsx.
 */
export function PillMorph({ context: rawContext, children }: { context?: PillContext | null; children: ReactNode }) {
  const context = normalizePillContext(rawContext);
  const contextId = context?.id ?? null;
  const [menuState, setMenuState] = useState<{ id: string | null; open: boolean }>({ id: null, open: false });
  const menuOpen = menuState.open && menuState.id === contextId;
  const toggle = useCallback(() => setMenuState((s) => ({ id: contextId, open: !(s.open && s.id === contextId) })), [contextId]);
  const menuBtnRef = useRef<HTMLButtonElement>(null);
  const mode = pillMode(Boolean(context), menuOpen);
  return (
    <div className="pill-morph" data-mode={mode} data-has-context={context ? "" : undefined} data-testid="pill-morph">
      <div className="pill-layer pill-layer--global" inert={mode === "context"}>
        {context ? (
          <button type="button" className="pill-icon-btn pill-icon-btn--menu" aria-label={PILL_MENU_LABEL} aria-expanded={menuOpen} data-testid="pill-menu-close" onClick={toggle}>
            <TabGlyph name="more" size={22} />
          </button>
        ) : null}
        {children}
      </div>
      {context ? <PillContextLayer key={context.id} context={context} hidden={mode === "menu"} menuOpen={menuOpen} menuBtnRef={menuBtnRef} onMenu={toggle} /> : null}
    </div>
  );
}

/** The page segment alone (no row to fold back to): the Fantasy Sim draft room, where no action bar is mounted. */
export function PillContextOnly({ context: rawContext }: { context: PillContext | null }) {
  const context = normalizePillContext(rawContext);
  const ref = useRef<HTMLButtonElement>(null);
  if (!context) return null;
  return (
    <div className="pill-morph" data-mode="context" data-has-context="" data-testid="pill-context-only">
      <PillContextLayer key={context.id} context={context} hidden={false} menuOpen={false} menuBtnRef={ref} onMenu={() => {}} noMenu />
    </div>
  );
}
