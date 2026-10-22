"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useAuth } from "@/context/AuthContext";
import { api, type TradeOutcomeHistoryResponse } from "@/lib/api";
import { TradeHistoryContent } from "@/components/TradeHistoryContent";
import { LoadingScreen } from "@/components/LoadingScreen";
import { onTradeOutcomeAnswered } from "@/lib/tradeOutcomeEvents";

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

    // Re-fetch quietly when the "Did this trade happen?" prompt records an
    // answer while this page is open, so the new row shows without a
    // reload. A failed refresh keeps the list already on screen.
    const unsubscribe = onTradeOutcomeAnswered(() => {
      api
        .getTradeOutcomeHistory()
        .then((result) => {
          if (!cancelled) setData(result);
        })
        .catch(() => {});
    });

    return () => {
      cancelled = true;
      unsubscribe();
    };
  }, [authLoading, session, router]);

  if (authLoading || (!data && !error)) {
    return (
      <LoadingScreen status="Loading Trade History…" />
    );
  }

  if (error || !data) {
    return (
      <main className="flex-1 flex items-center justify-center px-4">
        <p role="alert" style={{ color: "var(--color-danger)" }}>
          {error || "Could not load Trade History."}
        </p>
      </main>
    );
  }

  return <TradeHistoryContent data={data} />;
}
