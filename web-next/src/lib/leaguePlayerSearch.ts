import { useEffect, useState } from "react";

import { api, type RankedPlayer } from "@/lib/api";

const EMPTY: RankedPlayer[] = [];
export const PLAYER_SEARCH_MIN_CHARS = 2;
/** Rows the compact pickers (GM orb, Games add) show. */
export const PLAYER_SEARCH_MAX_RESULTS = 5;
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

export const PLAYER_LOOKUP_MAX_IDS = 25;

/** Players for `ids` that the loaded rankings `pool` does not already hold,
 * resolved by exact id over the whole league pool (so a player ranked below
 * the window still resolves from a URL/share link). Merge the result with
 * mergeSearchMatches. Returns [] when nothing is missing or on failure. */
export async function fetchMissingPlayersById(
  leagueId: string,
  lens: string,
  ids: readonly string[],
  pool: readonly RankedPlayer[],
): Promise<RankedPlayer[]> {
  const have = new Set(pool.map((p) => p.player_id));
  const missing = [...new Set(ids.filter((id) => id && !have.has(id)))];
  if (!leagueId || missing.length === 0) return [];
  const out: RankedPlayer[] = [];
  for (let i = 0; i < missing.length; i += PLAYER_LOOKUP_MAX_IDS) {
    try {
      const res = await api.getLeaguePlayersByIds(leagueId, missing.slice(i, i + PLAYER_LOOKUP_MAX_IDS), lens);
      out.push(...res.players);
    } catch {
      // Fail open: the windowed pool still works.
    }
  }
  return out;
}

/** Players matching `query` from the whole league pool, fetched server-side so
 * anyone ranked below the loaded rankings window is still searchable. Returns
 * [] for short queries and on failure (the windowed list keeps working).
 * `pending` is true from the first keystroke until the server answers, so a
 * picker can show "Searching..." instead of a premature "No players match". */
export function useLeaguePlayerSearchState(
  leagueId: string,
  lens: string,
  query: string,
): { players: RankedPlayer[]; pending: boolean } {
  // Results are stored with the key they answer, so a short/changed query is
  // derived to [] at render time instead of calling setState inside the effect.
  const [answer, setAnswer] = useState<{ key: string; players: RankedPlayer[] }>({ key: "", players: [] });
  const term = query.trim();
  const key = `${leagueId}|${lens}|${term}`;
  useEffect(() => {
    if (!leagueId || term.length < PLAYER_SEARCH_MIN_CHARS) return;
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
  const active = Boolean(leagueId) && term.length >= PLAYER_SEARCH_MIN_CHARS;
  const answered = active && answer.key === key;
  return { players: answered ? answer.players : EMPTY, pending: active && !answered };
}

/** Players only; see useLeaguePlayerSearchState. */
export function useLeaguePlayerSearch(leagueId: string, lens: string, query: string): RankedPlayer[] {
  return useLeaguePlayerSearchState(leagueId, lens, query).players;
}
