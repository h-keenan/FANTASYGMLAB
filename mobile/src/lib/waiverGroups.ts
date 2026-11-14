/**
 * Waiver list grouping (docs/ui-patterns.md "Module templates", Row): facts that every row of a list repeats are
 * said once for the group instead. Import-free, byte-identical twin of mobile/src/lib/waiverGroups.ts.
 */

/**
 * The cut that most of a list's adds share ("DROP Tutu Atwell" on every row): shown once as a group note. Only a real
 * group counts: the same drop player on at least two rows and on at least half of the rows that carry a drop
 * suggestion. Rows with a different cut keep their own one-line note (the override).
 */
export function sharedDropCandidate<T extends { drop_suggestion?: { drop: { player_id: string } | null } | null }>(
  players: readonly T[],
): { playerId: string; count: number; first: T } | null {
  const counts = new Map<string, { count: number; first: T }>();
  let withDrop = 0;
  for (const player of players) {
    const id = player.drop_suggestion?.drop?.player_id;
    if (!id) continue;
    withDrop += 1;
    const entry = counts.get(id);
    if (entry) entry.count += 1;
    else counts.set(id, { count: 1, first: player });
  }
  let best: { playerId: string; count: number; first: T } | null = null;
  for (const [playerId, entry] of counts) {
    if (!best || entry.count > best.count) best = { playerId, ...entry };
  }
  return best && best.count >= 2 && best.count * 2 >= withDrop ? best : null;
}

interface FaabLike {
  applicable?: boolean;
  dollars_known?: boolean;
  remaining?: number | null;
}

/** The bid line a whole group shares ("of $81 remaining"), so rows show just "$8–$12". Null when rows differ or any is not a bid. */
export function sharedBidNote(players: readonly { faab?: FaabLike | null }[]): string | null {
  const notes = new Set<string>();
  for (const player of players) {
    const faab = player.faab;
    if (faab == null || faab.applicable === false) return null;
    notes.add(faab.dollars_known && faab.remaining != null ? `of $${faab.remaining} remaining` : "of remaining FAAB");
  }
  return notes.size === 1 ? [...notes][0] : null;
}
