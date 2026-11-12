"use client";

import { useEffect, useState } from "react";

import { maskSavedLeagueRows } from "@/lib/privacy";
import { simImportableLeagues } from "@/lib/simGame";
import { supabase } from "@/lib/supabase";

export interface SimLeagueChoice {
  league_id: string;
  league_name: string | null;
}

/**
 * The account's saved leagues the GM game can start from (Sleeper only), for
 * "Start from one of my leagues". Read-only; `null` while loading, `[]` on any
 * failure so the option simply shows as unavailable.
 */
export function useSimLeagueChoices(enabled: boolean): SimLeagueChoice[] | null {
  const [rows, setRows] = useState<SimLeagueChoice[] | null>(null);
  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    supabase
      .from("saved_leagues")
      .select("league_id, league_name")
      .then(
        ({ data, error }) => {
          if (cancelled) return;
          setRows(error ? [] : simImportableLeagues(maskSavedLeagueRows((data ?? []) as SimLeagueChoice[])));
        },
        () => {
          if (!cancelled) setRows([]);
        },
      );
    return () => {
      cancelled = true;
    };
  }, [enabled]);
  return rows;
}
