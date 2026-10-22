"use client";

import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { useAuth } from "@/context/AuthContext";
import { useValuationLens } from "@/context/ValuationLensContext";
import { trackFeatureUse } from "@/lib/analytics";
import { api, type KeepersResponse, type MyTeamNeedsResponse, type MyTeamResponse, type TeamRanking } from "@/lib/api";
import { MyTeamContent } from "@/components/MyTeamContent";
import { ErrorState, reloadPage } from "@/components/ErrorState";
import { LoadingScreen } from "@/components/LoadingScreen";

export default function MyTeamPage() {
  const params = useParams<{ leagueId: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();
  const { session, loading: authLoading } = useAuth();

  const leagueId = decodeURIComponent(params.leagueId);
  const leagueName = searchParams.get("name") || leagueId;
  // Recommendation-compliance audit, Check 3 follow-up — My Team's own
  // injury-alert/value-trend GM Plan/Dashboard tiles already carry
  // route_player_id (see modules/dashboard_engine.py's build_injury_tile/
  // build_value_trend_tile) and already get threaded through as ?playerId=
  // by gamePlanTileHref (same as Waivers/Trade Hub, #1293) — this page just
  // wasn't reading it yet.
  const highlightPlayerId = searchParams.get("playerId") || undefined;
  const { lens, lensReady } = useValuationLens(leagueId);

  useEffect(() => {
    if (!session) return;
    trackFeatureUse("my_team_opened", { leagueId });
  }, [session, leagueId]);

  const [myTeam, setMyTeam] = useState<MyTeamResponse | null>(null);
  // Best-effort supplements — a Strength & Pressure/Team Snapshot field
  // simply doesn't render if either of these fails, same "degrade, don't
  // block the lineup" contract the mobile MyTeamScreen follows for its own
  // bonus Team Analytics section.
  const [needs, setNeeds] = useState<MyTeamNeedsResponse | null>(null);
  // GET .../team-rankings starts alongside the My Team request (it used to
  // wait for `myTeam.roster_id`); this page picks its own team out of the
  // result once both have landed.
  const [teamRankings, setTeamRankings] = useState<TeamRanking[] | null>(null);
  const [keepers, setKeepers] = useState<KeepersResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (authLoading) return;
    if (!session) {
      router.replace("/");
      return;
    }
    // First fetch waits only for the league type, so a redraft league is
    // requested once (as Non-Dynasty), not once as Dynasty and again.
    if (!lensReady) return;
    let cancelled = false;

    api
      .getMyTeam(leagueId, lens)
      .then((result) => {
        if (!cancelled) setMyTeam(result);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Could not load My Team.");
      });

    api
      .getMyTeamNeeds(leagueId, lens)
      .then((result) => {
        if (!cancelled) setNeeds(result);
      })
      .catch(() => {
        /* best-effort — Strength & Pressure/Position Groups just don't render */
      });

    api
      .getKeepers(leagueId, lens)
      .then((result) => {
        if (!cancelled) setKeepers(result);
      })
      .catch(() => {
        /* best-effort: keeper tags/candidates just don't render */
      });

    // Team Snapshot's ring/archetype/rank tiles.
    api
      .getTeamRankings(leagueId, lens)
      .then((result) => {
        if (!cancelled) setTeamRankings(result.teams);
      })
      .catch(() => {
        /* best-effort */
      });

    return () => {
      cancelled = true;
    };
  }, [authLoading, session, leagueId, lens, lensReady, router]);

  const teamRanking: TeamRanking | null =
    myTeam?.roster_id && teamRankings
      ? (teamRankings.find((team) => team.roster_id === myTeam.roster_id) ?? null)
      : null;
  const leagueSize = myTeam?.roster_id && teamRankings ? teamRankings.length : 0;

  if (authLoading || (!myTeam && !error)) {
    return (
      <LoadingScreen status="Loading My Team…" />
    );
  }

  if (error || !myTeam) {
    return (
      <ErrorState message={error || "Could not load My Team."} onRetry={reloadPage} />
    );
  }

  return (
    <MyTeamContent
      leagueName={leagueName}
      myTeam={myTeam}
      needs={needs}
      teamRanking={teamRanking}
      leagueSize={leagueSize}
      keepers={keepers}
      highlightPlayerId={highlightPlayerId}
    />
  );
}
