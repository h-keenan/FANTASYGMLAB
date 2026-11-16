"use client";

import { useEffect, useState } from "react";

import { api, type LeagueTeamRankingsResponse, type MatchupResponse, type MyTeamNeedsResponse } from "@/lib/api";

/** The three reads Today needs beyond the Dashboard payload (matchup, roster needs, league rankings). Each failing just hides its part. */
export function useTeamStatusData(
  leagueId: string,
  lens: string,
  enabled: boolean,
  teamRankings?: Promise<LeagueTeamRankingsResponse>,
  /** Requests the page already started (alongside the Dashboard call), so the
   * hero does not wait a full Dashboard round trip before asking for them. */
  prefetch?: TeamStatusPrefetch,
) {
  const [matchup, setMatchup] = useState<MatchupResponse | null>(null);
  const [needs, setNeeds] = useState<MyTeamNeedsResponse | null>(null);
  const [rankings, setRankings] = useState<LeagueTeamRankingsResponse | null>(null);
  // True once all three reads have landed or failed; until then Today holds
  // its place with a skeleton instead of popping in and pushing the page down.
  const [settled, setSettled] = useState(!enabled);
  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    const matchupRequest = prefetch?.matchup ?? api.getLeagueMatchup(leagueId, lens);
    const needsRequest = prefetch?.needs ?? api.getMyTeamNeeds(leagueId, lens);
    const rankingsRequest = teamRankings ?? api.getTeamRankings(leagueId, lens);
    const track = <T,>(request: Promise<T>, apply: (value: T) => void) =>
      request
        .then((value) => {
          if (!cancelled) apply(value);
        })
        .catch(() => {});
    void Promise.all([track(matchupRequest, setMatchup), track(needsRequest, setNeeds), track(rankingsRequest, setRankings)]).then(() => {
      if (!cancelled) setSettled(true);
    });
    return () => {
      cancelled = true;
    };
  }, [leagueId, lens, enabled, teamRankings, prefetch]);
  return { matchup, needs, rankings, settled };
}

export type TeamStatusPrefetch = { matchup: Promise<MatchupResponse>; needs: Promise<MyTeamNeedsResponse> };
