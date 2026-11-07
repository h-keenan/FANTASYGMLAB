"use client";

import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import { maskSavedLeagueRows } from "@/lib/privacy";
import { supabase } from "@/lib/supabase";

export interface DefaultLeague {
  /** How many leagues the account has saved. */
  count: number;
  /** The league a link can go straight to: the only one, else the last one the
   * account opened (when still saved). Null when there are several and no
   * known last league. */
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
      .then(async ({ data, error }) => {
        if (cancelled || error) return;
        const rows = maskSavedLeagueRows((data ?? []) as Array<{ league_id: string; league_name: string | null }>);
        const nameOf = (row: { league_id: string; league_name: string | null }) => row.league_name || row.league_id;
        let only = rows.length === 1 ? { leagueId: rows[0].league_id, leagueName: nameOf(rows[0]) } : null;
        if (!only && rows.length > 1) {
          // Several leagues: use the one they opened last instead of sending
          // them to the Portfolio to pick again.
          const last = await api.getDevicePreferences().then((p) => p.last_league, () => null);
          const match = last ? rows.find((row) => row.league_id === last.league_id) : undefined;
          if (match) only = { leagueId: match.league_id, leagueName: nameOf(match) };
        }
        if (!cancelled) setState({ count: rows.length, only });
      });
    return () => {
      cancelled = true;
    };
  }, []);
  return state;
}
