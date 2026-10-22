/**
 * Player-name matching for the GM orb's search field (tap-depth audit
 * 2026-10, proposal #3). Pure, so the node test runner covers it.
 *
 * Plain case-insensitive substring match, same as the Players screen's own
 * search, ranked so a name that starts with the query (or has a word that
 * does: "kel" -> "Travis Kelce") comes before a mid-word hit. Ties keep the
 * pool's own order, which is league rank.
 */

export const PLAYER_SEARCH_MIN_CHARS = 2;
export const PLAYER_SEARCH_MAX_RESULTS = 5;

export function matchPlayersByName<T extends { name: string | null }>(
  players: readonly T[],
  query: string,
  limit: number = PLAYER_SEARCH_MAX_RESULTS,
): T[] {
  const q = query.trim().toLowerCase();
  if (q.length < PLAYER_SEARCH_MIN_CHARS) return [];
  const starts: T[] = [];
  const wordStarts: T[] = [];
  const contains: T[] = [];
  for (const player of players) {
    const name = (player.name ?? '').toLowerCase();
    if (!name) continue;
    if (name.startsWith(q)) starts.push(player);
    else if (name.split(/[\s.'-]+/).some((word) => word.startsWith(q))) wordStarts.push(player);
    else if (name.includes(q)) contains.push(player);
  }
  return [...starts, ...wordStarts, ...contains].slice(0, limit);
}
