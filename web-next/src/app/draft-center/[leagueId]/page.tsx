"use client";

import { useParams, useRouter } from "next/navigation";
import { useSearchParams } from "@/lib/useSearchParams";
import { useEffect, useState } from "react";

import { useAuth } from "@/context/AuthContext";
import { useValuationLens } from "@/context/ValuationLensContext";
import { trackFeatureUse } from "@/lib/analytics";
import { api, type DraftCenterResponse,
  type DraftPickAsset, type LiveDraftDiscoveryResponse, type PositionNeedGroup } from "@/lib/api";
import { DraftCenterContent, parseDraftCenterTab, type DraftCenterTab } from "@/components/DraftCenterContent";
import { PremiumUpsellCard } from "@/components/PremiumUpsellCard";
import { ErrorState, reloadPage } from "@/components/ErrorState";
import { LoadingScreen } from "@/components/LoadingScreen";
import { UNNAMED_LEAGUE } from "@/lib/leagueName";
import { prospectsHref } from "@/lib/retiredRoutes";

export default function DraftCenterPage() {
  const params = useParams<{ leagueId: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();
  const { session, loading: authLoading } = useAuth();

  const leagueId = decodeURIComponent(params.leagueId);
  const leagueName = searchParams.get("name") || UNNAMED_LEAGUE;
  const { lens, lensReady } = useValuationLens(leagueId);

  // College prospect scouting moved to Players > Prospects (2026-11-16 nav consolidation): old Scouting links follow it.
  const wantsScouting = searchParams.get("tab") === "scouting";
  useEffect(() => {
    if (wantsScouting) router.replace(prospectsHref(leagueId, leagueName));
  }, [wantsScouting, leagueId, leagueName, router]);

  useEffect(() => {
    if (!session) return;
    trackFeatureUse("draft_center_opened", { leagueId });
  }, [session, leagueId]);

  const [draftCenter, setDraftCenter] = useState<DraftCenterResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Picks and the caller's own roster are additive to the page — neither
  // should be able to blank out the posture/insight cards that already
  // loaded, so both degrade quietly instead of blocking the page, same
  // contract mobile's DraftCenterScreen.tsx follows.
  const [picks, setPicks] = useState<DraftPickAsset[]>([]);
  const [needGroups, setNeedGroups] = useState<PositionNeedGroup[] | null>(null);
  const [myRosterId, setMyRosterId] = useState<string>("");
  // The Sleeper draft discovery decides whether the "Live room" tab exists (best-effort, never blocks the page).
  const [liveDiscovery, setLiveDiscovery] = useState<LiveDraftDiscoveryResponse | null>(null);

  useEffect(() => {
    if (authLoading) return;
    if (!session) {
      router.replace("/");
      return;
    }
    // Hold the first fetch until the league type is known (see ValuationLensContext), so a redraft
    // league is requested once as Non-Dynasty, not once as Dynasty and again after detection.
    if (!lensReady) return;
    let cancelled = false;

    api
      .getLeagueDraftCenter(leagueId, lens)
      .then((result) => {
        if (!cancelled) setDraftCenter(result);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Could not load Draft.");
      });

    api
      .getLeagueDraftPicks(leagueId, lens)
      .then((result) => {
        if (!cancelled) setPicks(result.picks);
      })
      .catch(() => {
        /* best-effort */
      });

    api
      .getLiveDraftDiscovery(leagueId)
      .then((result) => {
        if (!cancelled) setLiveDiscovery(result);
      })
      .catch(() => {
        /* best-effort: no discovery just means no Live room tab */
      });

    api
      .getMyTeamNeeds(leagueId, lens)
      .then((result) => {
        if (!cancelled) setNeedGroups(result.position_groups ?? null);
      })
      .catch(() => {
        /* best-effort: the league overlay just shows pick fits */
      });

    api
      .getMyRoster(leagueId)
      .then((result) => {
        if (!cancelled && result.roster) {
          setMyRosterId(String((result.roster as { roster_id?: unknown }).roster_id ?? ""));
        }
      })
      .catch(() => {
        /* best-effort */
      });

    return () => {
      cancelled = true;
    };
  }, [authLoading, session, leagueId, lens, lensReady, router]);

  // Keep ?tab= in the address bar so a tab is linkable/refreshable without a navigation.
  function syncTabToUrl(tab: DraftCenterTab) {
    const url = new URL(window.location.href);
    if (tab === "overview") url.searchParams.delete("tab");
    else url.searchParams.set("tab", tab);
    window.history.replaceState(null, "", url);
  }

  if (authLoading || (!draftCenter && !error)) {
    return (
      <LoadingScreen label="Draft" layout="list" />
    );
  }

  if (error || !draftCenter) {
    return (
      <ErrorState message={error || "Could not load Draft."} onRetry={reloadPage} />
    );
  }

  // Pro-only: the server returns a locked payload (no cards, no posture) for
  // Free callers; show the standard locked card instead of empty sections.
  if (draftCenter.is_premium === false) {
    return (
      <PremiumUpsellCard
        kicker="Draft"
        leagueName={leagueName}
        upsell={draftCenter.upsell ?? null}
        fallbackTitle="Know where you stand on draft capital"
        fallbackBody="Draft Center is a Pro feature: your draft posture, league-wide pick decision signals and the best trade partners for your picks. Start your free trial to unlock it."
      />
    );
  }

  return (
    <DraftCenterContent
      leagueId={leagueId}
      leagueName={leagueName}
      data={draftCenter}
      picks={picks}
      myRosterId={myRosterId}
      initialTab={parseDraftCenterTab(searchParams.get("tab"))}
      onTabChange={syncTabToUrl}
      needGroups={needGroups}
      liveDiscovery={liveDiscovery}
      lens={lens}
    />
  );
}
