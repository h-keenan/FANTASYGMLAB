"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useAuth } from "@/context/AuthContext";
import { api, type TradeOutcomeHistoryResponse } from "@/lib/api";
import { TradeHistoryContent } from "@/components/TradeHistoryContent";
import { ErrorState, reloadPage } from "@/components/ErrorState";
import { LoadingScreen } from "@/components/LoadingScreen";

// Like Portfolio, Trade History has no [leagueId] segment — the real
// current page (modules/trade_outcomes_page.py) and GET
// /v1/trade-outcomes/history both read every one of the signed-in user's
// confirmed trades across every league, never filtered to one. Mobile's
// TradeHistoryScreen.tsx (More -> Your Team) is the same: no leagueId param
// anywhere in the call.
export default function TradeHistoryPage() {
  const router = useRouter();
  const { session, loading: authLoading } = useAuth();

  const [data, setData] = useState<TradeOutcomeHistoryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (authLoading) return;
    if (!session) {
      router.replace("/");
      return;
    }
    let cancelled = false;

    api
      .getTradeOutcomeHistory()
      .then((result) => {
        if (!cancelled) setData(result);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Could not load Trade History.");
      });

    return () => {
      cancelled = true;
    };
  }, [authLoading, session, router]);

  if (authLoading || (!data && !error)) {
    return (
      <LoadingScreen status="Loading Trade History…" />
    );
  }

  if (error || !data) {
    return (
      <ErrorState message={error || "Could not load Trade History."} onRetry={reloadPage} />
    );
  }

  return <TradeHistoryContent data={data} />;
}
