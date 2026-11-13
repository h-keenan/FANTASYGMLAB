"use client";

import { useCallback, useState } from "react";

import type { SimCtx } from "@/components/SimGameParts";
import { api } from "@/lib/api";
import type { SimLineupResponse } from "@/lib/simGame";
import { simAutoSetMessage, simLineupDiff, simLineupIssues } from "@/lib/simLayout";

/**
 * Auto-set the best lineup (POST .../lineup/auto) and say what changed. Reads
 * the current lineup first so the toast can name the swap and the projected
 * gain ("Swapped X for Y, +7.5 proj") or say "Lineup is optimal". Gating
 * (premium preview, 409, 503) goes through ctx.call like every game action.
 * Mobile twin: mobile/src/components/useSimAutoSet.ts.
 */
export function useSimAutoSet(ctx: SimCtx, onApplied?: (lineup: SimLineupResponse) => void) {
  const { gameId, call, notify, bump, reloadGame } = ctx;
  const [busy, setBusy] = useState(false);
  const [optimalAtTick, setOptimalAtTick] = useState<number | null>(null);

  const run = useCallback(async () => {
    if (busy) return;
    setBusy(true);
    let before: SimLineupResponse | null = null;
    try {
      before = await api.getSimLineup(gameId);
    } catch {
      before = null;
    }
    const body = await call(() => api.autoSimLineup(gameId));
    setBusy(false);
    if (!body?.slots) return;
    const toSlots = (r: SimLineupResponse | null) => (r?.slots ?? []).map((s) => ({ slot: s.slot as string, player: s.player ? { id: s.player.id, name: s.player.name } : null }));
    const diff = simLineupDiff(toSlots(before), toSlots(body), before?.projected_total ?? null, body.projected_total ?? null);
    const issues = simLineupIssues(body.slots ?? [], body.warnings ?? []);
    const unfixed = issues.empty.length + issues.zero.length > 0;
    notify(simAutoSetMessage(diff, issues), diff.swaps.length && !unfixed ? "success" : "muted");
    if (diff.swaps.length === 0) {
      // "Optimal" only when nothing is left unfixed (no empty slot, no bye/out starter).
      if (!unfixed) setOptimalAtTick(ctx.tick);
      return;
    }
    onApplied?.(body);
    bump();
    void reloadGame();
  }, [busy, gameId, call, notify, bump, reloadGame, ctx.tick, onApplied]);

  return { run, busy, optimal: optimalAtTick === ctx.tick };
}
