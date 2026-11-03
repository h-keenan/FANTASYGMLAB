"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect } from "react";

import { LoadingScreen } from "@/components/LoadingScreen";
import { TradeOfferContent } from "@/components/TradeOfferContent";
import { useAuth } from "@/context/AuthContext";
import { useValuationLens } from "@/context/ValuationLensContext";
import { useSearchParams } from "@/lib/useSearchParams";

export default function TradeOfferPage() {
  const params = useParams<{ leagueId: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();
  const { session, loading: authLoading } = useAuth();
  const leagueId = decodeURIComponent(params.leagueId);
  const leagueName = searchParams.get("name") || leagueId;
  const playerId = searchParams.get("playerId") || "";
  const { lens } = useValuationLens(leagueId);

  useEffect(() => {
    if (!authLoading && !session) router.replace("/");
  }, [authLoading, session, router]);

  if (authLoading || !session) return <LoadingScreen status="Loading…" />;
  return <TradeOfferContent leagueId={leagueId} leagueName={leagueName} playerId={playerId} lens={lens} />;
}
