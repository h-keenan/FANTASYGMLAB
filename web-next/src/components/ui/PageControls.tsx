"use client";

import { useSyncExternalStore, type ReactNode } from "react";
import { createPortal } from "react-dom";

const noopSubscribe = () => () => {};

/** DOM id of the slot inside the page's one control row. */
export const PAGE_CONTROLS_SLOT_ID = "page-controls-slot";

/**
 * THE one control row of a page (UI audit batch H, docs/audits/2026-11-ui-audit-e2e.md P0-2): the page's own view switch (Players /
 * Prospects, NFL / My League, Season Outlook / Pick'em) and its filters share ONE 44px row, so the first module starts within the
 * 110px budget at 390px (`scripts/sim_layout_playwright/module_scan.mjs`). A child view (a week select, the Filters button, the
 * prospect selects) puts its controls into the same row with `<PageControl>` (a portal into the slot, like PageTitle's info slot), so
 * the row never grows a second line. The bottom margin pulls the first module up from the page gap to `--page-top-gap`.
 * Mobile twin: components/PageControlRow.tsx.
 */
export function PageControlsRow({ children, testId = "page-controls" }: { children?: ReactNode; testId?: string }) {
  return (
    <div className="page-controls" data-testid={testId}>
      {children}
      <div id={PAGE_CONTROLS_SLOT_ID} className="contents" />
    </div>
  );
}

function slotElement(): HTMLElement | null {
  return document.getElementById(PAGE_CONTROLS_SLOT_ID);
}

/** Renders its children into the page's control row; in its own flex row (so tests and a page without a row still work) when there is none. */
export function PageControl({ children }: { children: ReactNode }) {
  const slot = useSyncExternalStore(noopSubscribe, slotElement, () => null);
  return slot ? createPortal(children, slot) : <div className="flex items-center gap-2">{children}</div>;
}
