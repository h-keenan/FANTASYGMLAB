"use client";

import { useParams, useRouter } from "next/navigation";
import { useSearchParams } from "@/lib/useSearchParams";
import { useEffect, useState } from "react";

import { useAuth } from "@/context/AuthContext";
import { useValuationLens } from "@/context/ValuationLensContext";
import { trackFeatureUse } from "@/lib/analytics";
import { api, type KeepersResponse, type MyTeamNeedsResponse, type MyTeamResponse, type TeamRanking } from "@/lib/api";
import { MyTeamContent } from "@/components/MyTeamContent";
import { ErrorState, reloadPage } from "@/components/ErrorState";
import { SkeletonBlock } from "@/components/Skeleton";

/** Reserves the final page's block heights so the content doesn't jump. */
function MyTeamSkeleton({ leagueName }: { leagueName: string }) {
  const block = (height: number, key: string) => (
    <SkeletonBlock key={key} height={height} />
  );
  return (
    <main className="flex-1 flex flex-col gap-8 px-4 py-8 max-w-3xl w-full mx-auto" aria-busy="true">
      <header className="flex flex-col gap-1">
        <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          My Team
        </span>
        <h1 style={{ font: "var(--font-page-title)" }}>{leagueName}</h1>
      </header>
      <span className="sr-only" role="status">
        Loading My Team
      </span>
      {[block(190, "snapshot"), block(230, "analysis"), block(420, "roster"), block(110, "composition")]}
    </main>
  );
}

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
    return <MyTeamSkeleton leagueName={leagueName} />;
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
      onKeeperRoundPenalty={(penalty) => {
        // Optimistic: show the choice, then reload keeper numbers from the server.
        setKeepers((prev) => (prev ? { ...prev, round_penalty: penalty } : prev));
        api
          .setKeeperRoundPenalty(leagueId, penalty)
          .then(() => api.getKeepers(leagueId, lens))
          .then(setKeepers)
          .catch(() => {
            /* best-effort: the next load shows the stored value */
          });
      }}
      highlightPlayerId={highlightPlayerId}
    />
  );
}
