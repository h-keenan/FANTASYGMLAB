import { useEffect, useState } from "react";

import { api, type RankedPlayer } from "@/lib/api";

const EMPTY: RankedPlayer[] = [];
export const PLAYER_SEARCH_MIN_CHARS = 2;
export const PLAYER_SEARCH_DEBOUNCE_MS = 250;

/** Appends search matches the loaded rankings window does not already hold.
 * The window (top-N by value) keeps its order; extras are by definition ranked
 * below it, so they follow in the server's match order. Never drops a row. */
export function mergeSearchMatches(pool: RankedPlayer[], extras: RankedPlayer[]): RankedPlayer[] {
  if (extras.length === 0) return pool;
  const seen = new Set(pool.map((p) => p.player_id));
  const added = extras.filter((p) => !seen.has(p.player_id));
  return added.length === 0 ? pool : [...pool, ...added];
}

/** Players matching `query` from the whole league pool, fetched server-side so
 * anyone ranked below the loaded rankings window is still searchable. Returns
 * [] for short queries and on failure (the windowed list keeps working). */
export function useLeaguePlayerSearch(leagueId: string, lens: string, query: string): RankedPlayer[] {
  // Results are stored with the key they answer, so a short/changed query is
  // derived to [] at render time instead of calling setState inside the effect.
  const [answer, setAnswer] = useState<{ key: string; players: RankedPlayer[] }>({ key: "", players: [] });
  const term = query.trim();
  const key = `${leagueId}|${lens}|${term}`;
  useEffect(() => {
    if (term.length < PLAYER_SEARCH_MIN_CHARS) return;
    let cancelled = false;
    const timer = setTimeout(() => {
      api
        .searchLeaguePlayers(leagueId, term, lens)
        .then((res) => {
          if (!cancelled) setAnswer({ key, players: res.players });
        })
        .catch(() => {
          if (!cancelled) setAnswer({ key, players: [] });
        });
    }, PLAYER_SEARCH_DEBOUNCE_MS);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [leagueId, lens, term, key]);
  return term.length >= PLAYER_SEARCH_MIN_CHARS && answer.key === key ? answer.players : EMPTY;
}
