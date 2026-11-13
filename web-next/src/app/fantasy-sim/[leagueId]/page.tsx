"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect } from "react";

import { FantasySimContent } from "@/components/FantasySimContent";
import { LoadingScreen } from "@/components/LoadingScreen";
import { useAuth } from "@/context/AuthContext";
import { trackFeatureUse } from "@/lib/analytics";
import { useSearchParams } from "@/lib/useSearchParams";
import { UNNAMED_LEAGUE } from "@/lib/leagueName";

export default function FantasySimPage() {
  const params = useParams<{ leagueId: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();
  const { session, loading: authLoading } = useAuth();

  const leagueId = decodeURIComponent(params.leagueId);
  const leagueName = searchParams.get("name") || UNNAMED_LEAGUE;

  useEffect(() => {
    if (authLoading) return;
    if (!session) {
      router.replace("/");
      return;
    }
    trackFeatureUse("fantasy_sim_opened", { leagueId });
  }, [authLoading, session, leagueId, router]);

  if (authLoading || !session) return <LoadingScreen status="Loading your season outlook…" />;
  return <FantasySimContent leagueId={leagueId} leagueName={leagueName} />;
}
