import { useEffect, useState } from 'react';

import { api, type RankedPlayer, type ValuationLens } from './api';

const EMPTY: RankedPlayer[] = [];
export const PLAYER_SEARCH_MIN_CHARS = 2;
/** Rows the compact pickers (GM orb, Games add) show. */
export const PLAYER_SEARCH_MAX_RESULTS = 5;
export const PLAYER_SEARCH_DEBOUNCE_MS = 250;

/** Appends search matches the loaded rankings window does not already hold.
 * The window keeps its order; extras are ranked below it. Never drops a row. */
export function mergeSearchMatches(pool: RankedPlayer[], extras: RankedPlayer[]): RankedPlayer[] {
  if (extras.length === 0) return pool;
  const seen = new Set(pool.map((p) => p.player_id));
  const added = extras.filter((p) => !seen.has(p.player_id));
  return added.length === 0 ? pool : [...pool, ...added];
}

/** Players matching `query` from the whole league pool, fetched server-side so
 * anyone ranked below the loaded rankings window is still searchable. Returns
 * [] for short queries and on failure (the windowed list keeps working).
 * `pending` is true from the first keystroke until the server answers, so a
 * picker can show "Searching..." instead of a premature "No players match". */
export function useLeaguePlayerSearchState(
  leagueId: string,
  lens: ValuationLens,
  query: string,
  options?: { availableOnly?: boolean },
): { players: RankedPlayer[]; pending: boolean } {
  // Results are stored with the key they answer, so a short/changed query is
  // derived to [] at render time instead of calling setState inside the effect.
  const [answer, setAnswer] = useState<{ key: string; players: RankedPlayer[] }>({ key: '', players: [] });
  const term = query.trim();
  const availableOnly = options?.availableOnly === true;
  const key = `${leagueId}|${lens}|${availableOnly}|${term}`;
  useEffect(() => {
    if (!leagueId || term.length < PLAYER_SEARCH_MIN_CHARS) return;
    let cancelled = false;
    const timer = setTimeout(() => {
      api
        .searchLeaguePlayers(leagueId, term, { lens, availableOnly })
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
  }, [leagueId, lens, term, key, availableOnly]);
  const active = Boolean(leagueId) && term.length >= PLAYER_SEARCH_MIN_CHARS;
  const answered = active && answer.key === key;
  return { players: answered ? answer.players : EMPTY, pending: active && !answered };
}

/** Players only; see useLeaguePlayerSearchState. */
export function useLeaguePlayerSearch(
  leagueId: string,
  lens: ValuationLens,
  query: string,
  options?: { availableOnly?: boolean },
): RankedPlayer[] {
  return useLeaguePlayerSearchState(leagueId, lens, query, options).players;
}
