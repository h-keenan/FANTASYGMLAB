"use client";

import { useCallback, useEffect, useState } from "react";

import { supabase } from "@/lib/supabase";
import { maskSavedLeagueRows } from "@/lib/privacy";

export interface SavedLeagueRow {
  league_id: string;
  league_name: string | null;
}

export type SavedLeaguesStatus = "idle" | "loading" | "ready" | "error";

/**
 * The signed-in user's saved leagues for the header and the league switcher. Fetched once per league page (not lazily when the
 * switcher opens, so the header can resolve a league id to its real name when a link forgot `?name=`), with a real status:
 * a failed load is `error` with `reload()`, never an empty list that reads as "no other leagues".
 */
export function useSavedLeagues(enabled: boolean): { rows: SavedLeagueRow[]; status: SavedLeaguesStatus; reload: () => void } {
  const [rows, setRows] = useState<SavedLeagueRow[]>([]);
  const [status, setStatus] = useState<SavedLeaguesStatus>("idle");
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setStatus("loading");
    Promise.resolve(supabase.from("saved_leagues").select("league_id, league_name"))
      .then(({ data, error }) => {
        if (cancelled) return;
        if (error) {
          setStatus("error");
          return;
        }
        setRows(maskSavedLeagueRows((data ?? []) as SavedLeagueRow[]));
        setStatus("ready");
      })
      .catch(() => {
        if (!cancelled) setStatus("error");
      });
    return () => {
      cancelled = true;
    };
  }, [enabled, attempt]);

  const reload = useCallback(() => setAttempt((n) => n + 1), []);
  return { rows, status, reload };
}
