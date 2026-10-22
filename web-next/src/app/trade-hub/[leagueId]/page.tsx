"use client";

import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { useAuth } from "@/context/AuthContext";
import { useValuationLens } from "@/context/ValuationLensContext";
import { trackFeatureUse } from "@/lib/analytics";
import { api, type TradeHubResponse } from "@/lib/api";
import { TradeHubContent } from "@/components/TradeHubContent";
import { ErrorState, reloadPage } from "@/components/ErrorState";
import { LoadingScreen } from "@/components/LoadingScreen";

export default function TradeHubPage() {
  const params = useParams<{ leagueId: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();
  const { session, loading: authLoading } = useAuth();

  const leagueId = decodeURIComponent(params.leagueId);
  const leagueName = searchParams.get("name") || leagueId;
  // Recommendation-compliance audit, Check 3 — a GM Plan/Dashboard trade
  // tile's CTA now threads the headline idea's receive-side player through
  // here (see gamePlanTileHref/resolveGamePlanTargetPlayerId) instead of
  // landing on this generic board with no way to tell which idea it meant.
  const highlightPlayerId = searchParams.get("playerId") || undefined;
  const { lens, lensReady } = useValuationLens(leagueId);

  useEffect(() => {
    if (!session) return;
    trackFeatureUse("trade_hub_opened", { leagueId });
    // Deliberately NOT depending on `lens` -- a lens change re-renders this
    // page but isn't a new "open" of Trade Hub, and `once_key` (leagueId)
    // already dedupes a genuine remount for the same league anyway.
  }, [session, leagueId]);

  // Recommendation-compliance audit finding: this page used to hardcode
  // "retool" regardless of the caller's declared Team Situation, so ideas
  // were never generated under the user's own stated stance. The strategy
  // now comes from the declared stance, but the server resolves it
  // (strategy=auto, the same mapping GET .../team-stance returns), so the
  // idea request no longer waits for a stance round trip first. A server
  // that predates "auto" echoes it back unresolved; that case falls back to
  // the old stance-then-ideas sequence.
  const [tradeHub, setTradeHub] = useState<TradeHubResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (authLoading) return;
    if (!session) {
      router.replace("/");
      return;
    }
    // First fetch waits only for the league type, so a redraft league is
    // requested once (as Non-Dynasty), not once as Dynasty and again.
    if (!lensReady) return;
    let cancelled = false;

    api
      .getTradeHub(leagueId, "auto", lens)
      .then(async (result) => {
        if (result.team_strategy !== "auto") return result;
        const stance = await api.getTeamStance(leagueId).catch(() => null);
        return api.getTradeHub(leagueId, stance?.strategy || "retool", lens);
      })
      .then((result) => {
        if (!cancelled) setTradeHub(result);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Could not load Trade Hub.");
      });

    return () => {
      cancelled = true;
    };
  }, [authLoading, session, leagueId, lens, lensReady, router]);

  if (authLoading || (!tradeHub && !error)) {
    return (
      <LoadingScreen status="Loading Trade Hub…" />
    );
  }

  if (error || !tradeHub) {
    return (
      <ErrorState message={error || "Could not load Trade Hub."} onRetry={reloadPage} />
    );
  }

  return (
    <TradeHubContent
      leagueId={leagueId}
      leagueName={leagueName}
      data={tradeHub}
      lens={lens}
      highlightPlayerId={highlightPlayerId}
    />
  );
}
