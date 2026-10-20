"use client";

import { useParams, useRouter, useSearchParams } from "next/navigation";
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
  type TeamStanceResponse,
} from "@/lib/api";
import { GmPlanContent } from "@/components/GmPlanContent";
import { LoadingScreen } from "@/components/LoadingScreen";

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

    return () => {
      cancelled = true;
    };
  }, [authLoading, session, leagueId, lens, router]);

  if (authLoading || (!gmPlan && !error)) {
    return (
      <LoadingScreen status="Loading GM Plan…" />
    );
  }

  if (error || !gmPlan || !teamStance || !myTeam || !targets || !rankings) {
    return (
      <main className="flex-1 flex items-center justify-center px-4">
        <p role="alert" style={{ color: "var(--color-danger)" }}>
          {error || "Could not load GM Plan."}
        </p>
      </main>
    );
  }

  return (
    <GmPlanContent
      leagueId={leagueId}
      leagueName={leagueName}
      data={gmPlan}
      teamStance={teamStance}
      myTeam={myTeam}
      targets={targets.targets}
      rankings={rankings}
    />
  );
}
