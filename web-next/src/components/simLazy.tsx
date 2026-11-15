"use client";

import dynamic from "next/dynamic";
import { useEffect } from "react";

import { SkeletonCard } from "@/components/Skeleton";

// Perf pass 2026-11: Fantasy Sim opens on the Home tab, but SimGameContent used
// to statically pull in every stage and tab (draft, recaps, final, offseason,
// team/players/trades/league). Those only render after a tap or a stage change,
// so each is its own chunk. Chunks are warmed on idle (see useSimWarmChunks) so
// switching tabs stays instant instead of waiting on the network on a phone.
const loading = () => <SkeletonCard lines={4} />;

const loaders = {
  draft: () => import("@/components/SimGameDraft"),
  recap: () => import("@/components/SimRecapStory"),
  final: () => import("@/components/SimGameRecap"),
  offseason: () => import("@/components/SimGameOffseason"),
  team: () => import("@/components/SimGameTeam"),
  trades: () => import("@/components/SimGameTrades"),
  league: () => import("@/components/SimGameLeague"),
  simTo: () => import("@/components/SimToControl"),
};

export const SimGameDraft = dynamic(() => loaders.draft().then((m) => m.SimGameDraft), { loading });
export const SimDraftRecapView = dynamic(() => loaders.draft().then((m) => m.SimDraftRecapView), { loading });
export const SimWeekRecapStory = dynamic(() => loaders.recap().then((m) => m.SimWeekRecapStory), { loading });
export const SimFinalView = dynamic(() => loaders.final().then((m) => m.SimFinalView), { loading });
export const SimGameOffseason = dynamic(() => loaders.offseason().then((m) => m.SimGameOffseason), { loading });
export const SimTeamTab = dynamic(() => loaders.team().then((m) => m.SimTeamTab), { loading });
export const SimPlayersTab = dynamic(() => loaders.team().then((m) => m.SimPlayersTab), { loading });
export const SimTradesTab = dynamic(() => loaders.trades().then((m) => m.SimTradesTab), { loading });
export const SimLeagueTab = dynamic(() => loaders.league().then((m) => m.SimLeagueTab), { loading });
export const SimToResultView = dynamic(() => loaders.simTo().then((m) => m.SimToResultView), { loading });

/** Warm the lazy chunks once the browser is idle (no behavior change). */
export function useSimWarmChunks(): void {
  useEffect(() => {
    const warm = () => {
      // Rare stages (draft, final) stay cold: they cost bytes for most sessions.
      for (const load of [loaders.team, loaders.trades, loaders.league, loaders.recap, loaders.offseason, loaders.simTo]) void load().catch(() => undefined);
    };
    const w = window as Window & { requestIdleCallback?: (cb: () => void) => number; cancelIdleCallback?: (id: number) => void };
    if (w.requestIdleCallback) {
      const id = w.requestIdleCallback(warm);
      return () => w.cancelIdleCallback?.(id);
    }
    const t = window.setTimeout(warm, 2000);
    return () => window.clearTimeout(t);
  }, []);
}
