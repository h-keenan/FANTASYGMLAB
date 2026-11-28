"use client";

import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import { waiverCutFor, waiverLeadId, type DecisionItem } from "@/lib/decisionQueue";

/**
 * The cut the waivers read suggests for Today's lead waiver add, so the row can show the add -> drop pair. One small read, only
 * when the queue names a waiver add; failing just leaves the row without a pair. Mobile twin: the waivers query in DashboardScreen.
 */
export function useWaiverCut(leagueId: string, lens: string, enabled: boolean, items: ReadonlyArray<DecisionItem>) {
  const addId = enabled ? waiverLeadId(items) : null;
  const [cut, setCut] = useState<ReturnType<typeof waiverCutFor>>(null);
  useEffect(() => {
    if (!addId) return;
    let cancelled = false;
    api
      .getLeagueWaivers(leagueId, lens, 25)
      .then((waivers) => {
        if (!cancelled) setCut(waiverCutFor(waivers, addId));
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [leagueId, lens, addId]);
  return addId && cut?.addId === addId ? cut : null;
}
