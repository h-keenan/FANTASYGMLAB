"use client";

import { useRouter } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { FeaturesContent } from "@/components/FeaturesContent";
import { LoadingScreen } from "@/components/LoadingScreen";
import { useAuth } from "@/context/AuthContext";
import { api } from "@/lib/api";
import type { FeatureLeague } from "@/lib/featureCatalog";
import { supabase } from "@/lib/supabase";
import { useIsPro } from "@/lib/useIsPro";
import { useSearchParams } from "@/lib/useSearchParams";

/**
 * "What FantasyDesk can do" (feature map for users). Not league-scoped in the
 * URL: the league is `?league=&name=` when a link carries one, otherwise the
 * last league the account opened, otherwise the first saved league.
 */
function FeaturesPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { session, loading: authLoading } = useAuth();
  const isPro = useIsPro();
  const queryId = searchParams.get("league");
  const queryName = searchParams.get("name");
  const [fallback, setFallback] = useState<FeatureLeague | null | undefined>(undefined);

  useEffect(() => {
    if (authLoading) return;
    if (!session) {
      router.replace("/");
      return;
    }
    if (queryId) return;
    let cancelled = false;
    const done = (league: FeatureLeague | null) => {
      if (!cancelled) setFallback(league);
    };
    api
      .getDevicePreferences()
      .then(async (prefs) => {
        if (prefs.last_league) return done({ id: prefs.last_league.league_id, name: prefs.last_league.league_name });
        const { data } = await supabase.from("saved_leagues").select("league_id, league_name").limit(1);
        const first = data?.[0];
        done(first ? { id: first.league_id, name: first.league_name || first.league_id } : null);
      })
      .catch(() => done(null));
    return () => {
      cancelled = true;
    };
  }, [authLoading, session, router, queryId]);

  if (authLoading || !session) return <LoadingScreen status="Loading…" />;
  const league: FeatureLeague | null = queryId ? { id: queryId, name: queryName || queryId } : (fallback ?? null);
  if (!queryId && fallback === undefined) return <LoadingScreen status="Loading…" />;
  return <FeaturesContent league={league} isPro={isPro} />;
}

export default function FeaturesRoute() {
  return (
    <Suspense fallback={<LoadingScreen status="Loading…" />}>
      <FeaturesPage />
    </Suspense>
  );
}
