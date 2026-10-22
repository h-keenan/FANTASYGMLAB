/**
 * Trade Finder draft-pick selection helpers — pure, so they're covered by
 * the node test runner without rendering the screen.
 *
 * TRADE_FINDER_MAX_PICKS mirrors modules.trade_ideas.
 * TRADE_FINDER_MAX_SELECTED_PICKS: the server ignores any selected pick past
 * this many (it bounds the pick-package fan-out), so the picker stops there.
 */

export const TRADE_FINDER_MAX_PICKS = 4;

interface OwnablePick {
  pick_id: string;
  owner_roster_id: string;
  season: number | null;
  round: number | null;
}

/** Only picks this roster currently owns (GET .../draft-picks already
 * reflects Sleeper's traded-picks ownership), earliest season/round first. */
export function ownedPicksForRoster<T extends OwnablePick>(picks: T[], rosterId: string | null | undefined): T[] {
  const mine = String(rosterId ?? '');
  if (!mine) return [];
  return picks
    .filter((pick) => String(pick.owner_roster_id) === mine)
    .sort((a, b) => (a.season ?? 0) - (b.season ?? 0) || (a.round ?? 0) - (b.round ?? 0));
}

/** Toggle `id` in `selected`, refusing to add past `max`. Returns a new Set. */
export function toggleCappedSelection(
  selected: ReadonlySet<string>,
  id: string,
  max: number = TRADE_FINDER_MAX_PICKS,
): Set<string> {
  const next = new Set(selected);
  if (next.has(id)) next.delete(id);
  else if (next.size < max) next.add(id);
  return next;
}
