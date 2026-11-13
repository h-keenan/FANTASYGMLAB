import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import type { SimLeagueRosterTeam } from "@/lib/simGame";

export type SimLeagueRostersState =
  | { status: "loading" }
  | { status: "ready"; teams: SimLeagueRosterTeam[] }
  | { status: "error" };

/**
 * Every team's roster from ONE request (GET /league/rosters): the League tab's Teams and Players views and the
 * trade partner list. Refetches when `tick` changes (a move was made) or `attempt` is bumped (retry). Pass
 * `enabled: false` to hold the request until the view is opened.
 */
export function useSimLeagueRosters(gameId: string, tick: number, attempt = 0, enabled = true): SimLeagueRostersState {
  const [state, setState] = useState<{ key: string; value: SimLeagueRostersState } | null>(null);
  const key = `${gameId}:${tick}:${attempt}`;
  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    api.getSimLeagueRosters(gameId).then(
      (body) => {
        if (cancelled) return;
        setState({ key, value: body.reason || !body.teams ? { status: "error" } : { status: "ready", teams: body.teams } });
      },
      () => {
        if (!cancelled) setState({ key, value: { status: "error" } });
      },
    );
    return () => {
      cancelled = true;
    };
  }, [gameId, key, enabled]);
  // Keep showing the last good data while a refresh is in flight (no flash to a skeleton after a move).
  if (!state) return { status: "loading" };
  if (state.key !== key && state.value.status === "error") return { status: "loading" };
  return state.value;
}
