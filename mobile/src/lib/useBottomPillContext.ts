"use client";

import { useEffect, useState, useSyncExternalStore } from "react";

import type { PillContext } from "./bottomNav.ts";
import { getPillState, getServerPillState, setPillContext, subscribePill } from "./bottomPillStore.ts";

/**
 * A page hands the smart pill its context: page tabs (the page-family tabs), which one is lit, one primary action.
 *
 *   const pillOwnsTabs = useBottomPillContext({ id: "team", label: "Team sections", tabs, activeKey, onSelect, primary });
 *   {!pillOwnsTabs ? <PageTabs .../> : null}
 *
 * Returns true while the pill is actually on screen (phone shell bar mounted) and showing THIS context, so the page
 * drops its own top tab row only then: consolidate, never remove. Desktop, the flag off and signed-out pages keep the
 * in-page tabs. Pass null to register nothing (a page can call it unconditionally). Twin: mobile useBottomPillContext.
 */
export function useBottomPillContext(ctx: PillContext | null): boolean {
  const [who] = useState(() => ({}));
  useEffect(() => {
    setPillContext(who, ctx);
  });
  useEffect(() => () => setPillContext(who, null), [who]);
  const state = useSyncExternalStore(subscribePill, getPillState, getServerPillState);
  return Boolean(ctx && state.barPresent && state.ctx && state.ctx.id === ctx.id);
}
