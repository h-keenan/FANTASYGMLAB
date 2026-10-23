"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect } from "react";

import { useSearchParams } from "@/lib/useSearchParams";
import { useAuth } from "@/context/AuthContext";
import { GamesContent } from "@/components/GamesContent";
import { LoadingScreen } from "@/components/LoadingScreen";

export default function GamesPage() {
  const params = useParams<{ leagueId: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();
  const { session, loading: authLoading } = useAuth();

  const leagueId = decodeURIComponent(params.leagueId);
  const leagueName = searchParams.get("name") || leagueId;

  useEffect(() => {
    if (!authLoading && !session) router.replace("/");
  }, [authLoading, session, router]);

  if (authLoading || !session) return <LoadingScreen status="Loading Games…" />;
  return <GamesContent leagueId={leagueId} leagueName={leagueName} />;
}
