"use client";

import { useEffect, useState } from "react";

import { maskSavedLeagueRows } from "@/lib/privacy";
import { supabase } from "@/lib/supabase";

export interface DefaultLeague {
  /** How many leagues the account has saved. */
  count: number;
  /** Set only when there is exactly one, so a link can go straight to it. */
  only: { leagueId: string; leagueName: string } | null;
}

/**
 * For league-less pages (News, Trade History, Community) that want a
 * "next step" link into a league page. One saved league: a direct link.
 * Several: callers link to the Portfolio instead of guessing. `null` until
 * known and on any failure, so the link is simply not shown.
 */
export function useDefaultLeague(): DefaultLeague | null {
  const [state, setState] = useState<DefaultLeague | null>(null);
  useEffect(() => {
    let cancelled = false;
    supabase
      .from("saved_leagues")
      .select("league_id, league_name")
      .then(({ data, error }) => {
        if (cancelled || error) return;
        const rows = maskSavedLeagueRows((data ?? []) as Array<{ league_id: string; league_name: string | null }>);
        setState({
          count: rows.length,
          only: rows.length === 1 ? { leagueId: rows[0].league_id, leagueName: rows[0].league_name || rows[0].league_id } : null,
        });
      });
    return () => {
      cancelled = true;
    };
  }, []);
  return state;
}
