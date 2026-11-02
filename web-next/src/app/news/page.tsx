"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useAuth } from "@/context/AuthContext";
import { trackFeatureUse } from "@/lib/analytics";
import { api, type NewsResponse } from "@/lib/api";
import { NewsContent } from "@/components/NewsContent";
import { ErrorState, reloadPage } from "@/components/ErrorState";
import { LoadingScreen } from "@/components/LoadingScreen";

// Like Portfolio, News has no [leagueId] segment — GET /v1/news is a
// general, non-roster-scoped feed for anyone, not "your team's" news (see
// that endpoint's own docstring in services/mobile_api_service.py).
export default function NewsPage() {
  const router = useRouter();
  const { session, loading: authLoading } = useAuth();

  const [data, setData] = useState<NewsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
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
      ? api.getPlayerNews(filter.playerId, 10).then((result) => ({ ok: result.ok, items: result.items }))
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

  if (authLoading || (!data && !error)) {
    return (
      <LoadingScreen status="Loading News…" />
    );
  }

  if (error || !data) {
    return (
      <ErrorState message={error || "Could not load News."} onRetry={reloadPage} />
    );
  }

  return <NewsContent data={data} playerName={filter ? filter.name || "this player" : null} />;
}
