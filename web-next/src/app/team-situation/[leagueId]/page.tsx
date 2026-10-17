"use client";

import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { useAuth } from "@/context/AuthContext";
import { api, type GmTargetsResponse, type MyTeamResponse, type TeamStanceResponse } from "@/lib/api";
import { TeamSituationContent } from "@/components/TeamSituationContent";
import { LoadingScreen } from "@/components/LoadingScreen";

export default function TeamSituationPage() {
  const params = useParams<{ leagueId: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();
  const { session, loading: authLoading } = useAuth();

  const leagueId = decodeURIComponent(params.leagueId);
  const leagueName = searchParams.get("name") || leagueId;

  const [teamStance, setTeamStance] = useState<TeamStanceResponse | null>(null);
  const [myTeam, setMyTeam] = useState<MyTeamResponse | null>(null);
  const [targets, setTargets] = useState<GmTargetsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (authLoading) return;
    if (!session) {
      router.replace("/");
      return;
    }
    let cancelled = false;

    Promise.all([api.getTeamStance(leagueId), api.getMyTeam(leagueId), api.getGmTargets(leagueId)])
      .then(([stanceResult, teamResult, targetsResult]) => {
        if (!cancelled) {
          setTeamStance(stanceResult);
          setMyTeam(teamResult);
          setTargets(targetsResult);
        }
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Could not load Team Situation.");
      });

    return () => {
      cancelled = true;
    };
  }, [authLoading, session, leagueId, router]);

  if (authLoading || (!teamStance && !myTeam && !targets && !error)) {
    return (
      <LoadingScreen status="Loading Team Situation…" />
    );
  }

  if (error || !teamStance || !myTeam || !targets) {
    return (
      <main className="flex-1 flex items-center justify-center px-4">
        <p role="alert" style={{ color: "var(--color-danger)" }}>
          {error || "Could not load Team Situation."}
        </p>
      </main>
    );
  }

  return (
    <TeamSituationContent
      leagueId={leagueId}
      leagueName={leagueName}
      teamStance={teamStance}
      myTeam={myTeam}
      targets={targets.targets}
    />
  );
}
