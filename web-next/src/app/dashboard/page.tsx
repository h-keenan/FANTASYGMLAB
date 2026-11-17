"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { LoadingScreen } from "@/components/LoadingScreen";
import { useAuth } from "@/context/AuthContext";
import { api } from "@/lib/api";
import { dashboardRedirectTarget } from "@/lib/dashboardRedirect";
import { maskSavedLeagueRows } from "@/lib/privacy";
import { supabase } from "@/lib/supabase";

/** /dashboard with no league id: send the user to their last/primary league's dashboard instead of a 404. */
export default function DashboardIndexPage() {
  const router = useRouter();
  const { session, loading } = useAuth();

  useEffect(() => {
    if (loading) return;
    if (!session) {
      router.replace(dashboardRedirectTarget(false, [], null));
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const { data } = await supabase.from("saved_leagues").select("league_id, league_name");
        const leagues = maskSavedLeagueRows((data ?? []) as Array<{ league_id: string; league_name: string | null }>);
        const last = leagues.length > 1 ? await api.getDevicePreferences().then((p) => p.last_league, () => null) : null;
        if (!cancelled) router.replace(dashboardRedirectTarget(true, leagues, last?.league_id ?? null));
      } catch {
        if (!cancelled) router.replace("/connect-league");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [loading, session, router]);

  return <LoadingScreen label="Dashboard" />;
}
