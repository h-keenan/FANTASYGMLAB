"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useAuth } from "@/context/AuthContext";
import { trackFeatureUse } from "@/lib/analytics";
import { api, type AlertsResponse, type NewsResponse } from "@/lib/api";
import { useDefaultLeague } from "@/lib/useDefaultLeague";
import { NewsContent } from "@/components/NewsContent";
import { NewsLeagueTab } from "@/components/NewsLeagueTab";
import { UNNAMED_LEAGUE } from "@/lib/leagueName";
import { parseNewsTab, type NewsTab } from "@/lib/newsLinks";
import { parseRecapsTab, parseRoundupWeek } from "@/lib/pageTabs";
import { ErrorState, reloadPage } from "@/components/ErrorState";
import { LoadingScreen } from "@/components/LoadingScreen";

// Like Portfolio, News has no [leagueId] segment — GET /v1/news is a
// general, non-roster-scoped feed for anyone (see that endpoint's own docstring
// in services/mobile_api_service.py). The roster-first digest on top comes from
// the account's default league's alerts (the roster-matched feed), when it has one.
export default function NewsPage() {
  const router = useRouter();
  const { session, loading: authLoading } = useAuth();

  const [data, setData] = useState<NewsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [alerts, setAlerts] = useState<AlertsResponse | null>(null);
  const defaultLeague = useDefaultLeague();
  // /news?player=<id>&name=<name> (from the quick view's "See all news").
  // Read once from the URL on the client (useSearchParams would force a
  // Suspense boundary around the page). Both server and first client render
  // show only the loading screen, so there is no visible mismatch.
  const [filter] = useState<{ playerId: string; name: string } | null | undefined>(() => {
    if (typeof window === "undefined") return undefined;
    const params = new URLSearchParams(window.location.search);
    const playerId = params.get("player");
    return playerId ? { playerId, name: params.get("name") || "" } : null;
  });
  // News has two tabs (2026-11-16 nav consolidation): NFL, and My League (the weekly recap, formerly League Recaps).
  // `?tab=league&league=<id>&name=<n>[&recaps=roundup&week=N]` is what the retired /league-recaps route, push deep
  // links and the orb open. Read once from the URL, like the player filter above.
  const [initialUrl] = useState(() => {
    if (typeof window === "undefined") return null;
    const params = new URLSearchParams(window.location.search);
    const leagueId = params.get("league");
    return {
      tab: parseNewsTab(params.get("tab")),
      league: leagueId ? { leagueId, leagueName: params.get("name") || UNNAMED_LEAGUE } : null,
      recapsTab: parseRecapsTab(params.get("recaps")),
      week: parseRoundupWeek(params.get("week")),
    };
  });
  const [tab, setTab] = useState<NewsTab>(initialUrl?.tab ?? "nfl");
  const leagueFromUrl = initialUrl?.league ?? null;
  const rosterLeagueId = leagueFromUrl?.leagueId ?? defaultLeague?.only?.leagueId ?? null;
  const recapLeague = leagueFromUrl ?? defaultLeague?.only ?? null;

  useEffect(() => {
    if (!session) return;
    trackFeatureUse("news_opened");
  }, [session]);

  useEffect(() => {
    if (authLoading || filter === undefined) return;
    if (!session) {
      router.replace("/");
      return;
    }
    let cancelled = false;

    const request: Promise<NewsResponse> = filter
      ? api.getPlayerNews(filter.playerId, 10, { groupDuplicates: true }).then((result) => ({ ok: result.ok, items: result.items }))
      : api.getNews();
    request
      .then((result) => {
        if (!cancelled) setData(result);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Could not load News.");
      });

    return () => {
      cancelled = true;
    };
  }, [authLoading, session, router, filter]);

  useEffect(() => {
    if (!session || !rosterLeagueId) return;
    let cancelled = false;
    api
      .getLeagueAlerts(rosterLeagueId, 30)
      .then((result) => {
        if (!cancelled) setAlerts(result);
      })
      .catch(() => {
        /* the league-wide feed still loads; the digest just has no roster section */
      });
    return () => {
      cancelled = true;
    };
  }, [session, rosterLeagueId]);

  if (authLoading || (!data && !error)) {
    return (
      <LoadingScreen label="News" layout="list" />
    );
  }

  if (error || !data) {
    return (
      <ErrorState message={error || "Could not load News."} onRetry={reloadPage} />
    );
  }

  const changeTab = (next: NewsTab) => {
    setTab(next);
    // Keep ?tab= in the address bar so a tab is linkable/refreshable without a navigation.
    const url = new URL(window.location.href);
    if (next === "nfl") url.searchParams.delete("tab");
    else url.searchParams.set("tab", next);
    window.history.replaceState(null, "", url);
  };

  return (
    <NewsContent
      data={data}
      playerName={filter ? filter.name || "this player" : null}
      alerts={filter ? null : alerts}
      tab={tab}
      onTabChange={changeTab}
      leagueTab={
        // The league is still being looked up (default league): hold the tab body instead of flashing "Pick a league".
        tab === "league" && !recapLeague && defaultLeague === null ? null : (
          <NewsLeagueTab league={recapLeague} recapsTab={initialUrl?.recapsTab} week={initialUrl?.week} />
        )
      }
    />
  );
}
