"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect } from "react";

import { useAuth } from "@/context/AuthContext";
import { GuessThePlayerLeaderboardContent } from "@/components/GuessThePlayerLeaderboardContent";
import { LoadingScreen } from "@/components/LoadingScreen";

export default function GuessThePlayerLeaderboardPage() {
  const params = useParams<{ leagueId: string }>();
  const router = useRouter();
  const { session, loading: authLoading } = useAuth();

  const leagueId = decodeURIComponent(params.leagueId);

  useEffect(() => {
    if (authLoading) return;
    if (!session) {
      router.replace("/");
    }
  }, [authLoading, session, router]);

  if (authLoading || !session) {
    return <LoadingScreen status="Loading the leaderboard…" />;
  }

  return <GuessThePlayerLeaderboardContent leagueId={leagueId} />;
}
