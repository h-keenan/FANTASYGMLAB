"use client";

import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { useAuth } from "@/context/AuthContext";
import { useValuationLens } from "@/context/ValuationLensContext";
import { trackFeatureUse } from "@/lib/analytics";
import { api, type MyTeamNeedsResponse, type MyTeamResponse, type TeamRanking } from "@/lib/api";
import { MyTeamContent } from "@/components/MyTeamContent";
import { LoadingScreen } from "@/components/LoadingScreen";

export default function MyTeamPage() {
  const params = useParams<{ leagueId: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();
  const { session, loading: authLoading } = useAuth();

  const leagueId = decodeURIComponent(params.leagueId);
  const leagueName = searchParams.get("name") || leagueId;
  const { lens } = useValuationLens(leagueId);

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
  const [teamRanking, setTeamRanking] = useState<TeamRanking | null>(null);
  const [leagueSize, setLeagueSize] = useState(0);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (authLoading) return;
    if (!session) {
      router.replace("/");
      return;
    }
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

    return () => {
      cancelled = true;
    };
  }, [authLoading, session, leagueId, lens, router]);

  // Team Snapshot's ring/archetype/rank tiles — a separate effect because
  // the match-up needs `myTeam.roster_id`, which only arrives once the
  // fetch above resolves.
  useEffect(() => {
    if (!myTeam?.roster_id) return;
    let cancelled = false;
    api
      .getTeamRankings(leagueId, lens)
      .then((result) => {
        if (cancelled) return;
        setLeagueSize(result.teams.length);
        const mine = result.teams.find((team) => team.roster_id === myTeam.roster_id) ?? null;
        setTeamRanking(mine);
      })
      .catch(() => {
        /* best-effort */
      });
    return () => {
      cancelled = true;
    };
  }, [leagueId, lens, myTeam?.roster_id]);

  if (authLoading || (!myTeam && !error)) {
    return (
      <LoadingScreen status="Loading My Team…" />
    );
  }

  if (error || !myTeam) {
    return (
      <main className="flex-1 flex items-center justify-center px-4">
        <p role="alert" style={{ color: "var(--color-danger)" }}>
          {error || "Could not load My Team."}
        </p>
      </main>
    );
  }

  return (
    <MyTeamContent leagueName={leagueName} myTeam={myTeam} needs={needs} teamRanking={teamRanking} leagueSize={leagueSize} />
  );
}
