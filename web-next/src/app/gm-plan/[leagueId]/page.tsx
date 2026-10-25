"use client";

import { useParams, useRouter } from "next/navigation";
import { useSearchParams } from "@/lib/useSearchParams";
import { useEffect, useState } from "react";

import { useAuth } from "@/context/AuthContext";
import { useValuationLens } from "@/context/ValuationLensContext";
import { trackFeatureUse } from "@/lib/analytics";
import {
  api,
  type GmPlanResponse,
  type GmTargetsResponse,
  type LeagueRankingsResponse,
  type MyTeamResponse,
  type PlayoffOddsTeam,
  type TeamRanking,
  type TeamStanceResponse,
} from "@/lib/api";
import { GmPlanContent } from "@/components/GmPlanContent";
import { GmPlanSkeleton, isGmPlanTab } from "@/components/GmPlanSections";
import { buildPlanSnapshot } from "@/lib/gmPlanSnapshot";
import { ErrorState, reloadPage } from "@/components/ErrorState";

export default function GmPlanPage() {
  const params = useParams<{ leagueId: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();
  const { session, loading: authLoading } = useAuth();

  const leagueId = decodeURIComponent(params.leagueId);
  const leagueName = searchParams.get("name") || leagueId;
  const { lens } = useValuationLens(leagueId);

  const [gmPlan, setGmPlan] = useState<GmPlanResponse | null>(null);
  const [teamStance, setTeamStance] = useState<TeamStanceResponse | null>(null);
  const [myTeam, setMyTeam] = useState<MyTeamResponse | null>(null);
  const [targets, setTargets] = useState<GmTargetsResponse | null>(null);
  const [rankings, setRankings] = useState<LeagueRankingsResponse | null>(null);
  // Best-effort Plan Snapshot sources: a tile just doesn't render if its call fails.
  const [teamRankings, setTeamRankings] = useState<TeamRanking[] | null>(null);
  const [oddsTeams, setOddsTeams] = useState<PlayoffOddsTeam[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Audit finding, 2026-10-20: gm_plan_opened (already in TRACKED_EVENTS,
  // already in ROUTE_EVENT_MAP/FEATURE_EVENT_MAP/CORE_FEATURE_EVENTS) had
  // no caller anywhere in web-next -- same pattern as every other core
  // surface's page-open event (see trade-hub/my-team/waivers/draft-center).
  useEffect(() => {
    if (!session) return;
    trackFeatureUse("gm_plan_opened", { leagueId });
  }, [session, leagueId]);

  useEffect(() => {
    if (authLoading) return;
    if (!session) {
      router.replace("/");
      return;
    }
    let cancelled = false;

    // Revision 20 (2026-10-18): GM Plan absorbed Team Situation (stance +
    // Protected Players) and GM Targets (the Watching list) — see
    // GmPlanContent's own docstring. One page now needs all five of these,
    // same five calls the two standalone pages made between them before.
    Promise.all([
      api.getGmPlan(leagueId, lens),
      api.getTeamStance(leagueId),
      api.getMyTeam(leagueId, lens),
      api.getGmTargets(leagueId),
      api.getLeagueRankings(leagueId, lens),
    ])
      .then(([gmPlanResult, stanceResult, teamResult, targetsResult, rankingsResult]) => {
        if (!cancelled) {
          setGmPlan(gmPlanResult);
          setTeamStance(stanceResult);
          setMyTeam(teamResult);
          setTargets(targetsResult);
          setRankings(rankingsResult);
        }
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Could not load GM Plan.");
      });

    api
      .getTeamRankings(leagueId, lens)
      .then((result) => {
        if (!cancelled) setTeamRankings(result.teams);
      })
      .catch(() => {});
    api
      .getLeaguePlayoffOdds(leagueId, lens)
      .then((result) => {
        if (!cancelled) setOddsTeams(result.teams);
      })
      .catch(() => {});

    return () => {
      cancelled = true;
    };
  }, [authLoading, session, leagueId, lens, router]);

  if (authLoading || (!gmPlan && !error)) {
    return <GmPlanSkeleton leagueName={leagueName} />;
  }

  if (error || !gmPlan || !teamStance || !myTeam || !targets || !rankings) {
    return (
      <ErrorState message={error || "Could not load GM Plan."} onRetry={reloadPage} />
    );
  }

  const rosterId = myTeam.roster_id;
  const snapshot = buildPlanSnapshot(
    teamRankings?.find((team) => team.roster_id === rosterId) ?? null,
    teamRankings?.length ?? 0,
    oddsTeams?.find((team) => team.roster_id === rosterId) ?? null,
  );
  const tabParam = searchParams.get("tab");

  return (
    <GmPlanContent
      snapshot={snapshot}
      initialTab={isGmPlanTab(tabParam) ? tabParam : undefined}
      leagueId={leagueId}
      leagueName={leagueName}
      data={gmPlan}
      teamStance={teamStance}
      myTeam={myTeam}
      targets={targets.targets}
      targetsLimit={{ freeLimit: targets.free_limit, isPremium: targets.is_premium }}
      rankings={rankings}
    />
  );
}
