"use client";

import { useParams, useRouter } from "next/navigation";
import { useSearchParams } from "@/lib/useSearchParams";
import { useEffect, useState } from "react";

import { useAuth } from "@/context/AuthContext";
import { useValuationLens } from "@/context/ValuationLensContext";
import { trackFeatureUse } from "@/lib/analytics";
import {
  api,
  type DraftPickAsset,
  type MyRosterResponse,
  type RankedPlayer,
  type TeamProfile,
} from "@/lib/api";
import { idpTradePoolPlayers } from "@/lib/idpPresentation";
import { TradeAnalyzerContent } from "@/components/TradeAnalyzerContent";
import { ErrorState, reloadPage } from "@/components/ErrorState";
import { bridgeTradeFromSearch } from "@/lib/tradeBridge";
import { LoadingScreen } from "@/components/LoadingScreen";

interface LoadedData {
  myRoster: MyRosterResponse;
  rankings: RankedPlayer[];
  picks: DraftPickAsset[];
  rosters: Array<Record<string, unknown>>;
  teamProfiles: Record<string, TeamProfile>;
}

export default function TradeAnalyzerPage() {
  const params = useParams<{ leagueId: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();
  const { session, loading: authLoading } = useAuth();

  const leagueId = decodeURIComponent(params.leagueId);
  const leagueName = searchParams.get("name") || leagueId;
  // Players' "Add to Trade" quick-add (Revision 20) threads the tapped
  // player through here as ?playerId=, the same gamePlanTileHref
  // convention Waivers/Trade Hub already read — TradeAnalyzerContent
  // resolves which roster owns it and pre-populates the builder on mount.
  const quickAddPlayerId = searchParams.get("playerId") || undefined;
  // Public Trade Analyzer bridge: ?a=&b= carried through sign-up (lib/tradeBridge.ts).
  const bridgeTrade = bridgeTradeFromSearch(`a=${searchParams.get("a") ?? ""}&b=${searchParams.get("b") ?? ""}`);
  const { lens } = useValuationLens(leagueId);

  const [data, setData] = useState<LoadedData | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Audit finding, 2026-10-20: Trade Analyzer was the one core surface with
  // zero analytics wiring at all (trade_hub_opened/my_team_opened/
  // waivers_opened/draft_center_opened/live_draft_opened all already fire
  // their own page-open event from this exact pattern) -- trade_analyzer_
  // opened was already in modules.launch_analytics.TRACKED_EVENTS and even
  // has a Founder Analytics dashboard label, it just never had a caller.
  useEffect(() => {
    if (!session) return;
    trackFeatureUse("trade_analyzer_opened", { leagueId });
  }, [session, leagueId]);

  useEffect(() => {
    if (authLoading) return;
    if (!session) {
      router.replace("/");
      return;
    }
    let cancelled = false;

    Promise.all([
      api.getMyRoster(leagueId),
      api.getLeagueRankings(leagueId, lens),
      // Picks/rosters/team-profiles can legitimately 404/empty for a league
      // with no draft-capital data yet (startup drafts, degraded ESPN
      // imports) — same graceful-empty fallback mobile's own screen uses,
      // so a roster-browse list with no picks never blocks the page.
      api.getLeagueDraftPicks(leagueId, lens).catch(() => ({ ok: true as const, picks: [], reason: "unavailable" })),
      api.getLeagueRosters(leagueId).catch(() => ({ ok: true as const, rosters: [] })),
      api.getLeagueTeamProfiles(leagueId).catch(() => ({ ok: true as const, profiles: {} })),
      // IDP leagues only (`idp: false` otherwise); a failure leaves offense untouched.
      api.getLeagueIdpValues(leagueId, { includeBelow: true }).catch(() => null),
    ])
      .then(([myRoster, rankingsResult, picksResult, rostersResult, teamProfilesResult, idpResult]) => {
        if (cancelled) return;
        setData({
          myRoster,
          rankings: [...rankingsResult.players, ...idpTradePoolPlayers(idpResult)],
          picks: picksResult.picks,
          rosters: rostersResult.rosters,
          teamProfiles: teamProfilesResult.profiles,
        });
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Could not load Trade Analyzer.");
      });

    return () => {
      cancelled = true;
    };
  }, [authLoading, session, leagueId, lens, router]);

  if (authLoading || (!data && !error)) {
    return (
      <LoadingScreen status="Loading Trade Analyzer…" />
    );
  }

  if (error || !data) {
    return (
      <ErrorState message={error || "Could not load Trade Analyzer."} onRetry={reloadPage} />
    );
  }

  return (
    <TradeAnalyzerContent
      leagueId={leagueId}
      leagueName={leagueName}
      myRoster={data.myRoster}
      rankings={data.rankings}
      picks={data.picks}
      rosters={data.rosters}
      teamProfiles={data.teamProfiles}
      quickAddPlayerId={quickAddPlayerId}
      bridgeTrade={bridgeTrade}
          lens={lens}
    />
  );
}
