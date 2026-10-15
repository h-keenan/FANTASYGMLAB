/**
 * Players / Asset Explorer (Revision 16) presentation helpers — pure
 * search/filter predicates only. Ranking/valuation itself is already
 * computed server-side (GET .../leagues/{id}/rankings, the same endpoint
 * GM Targets, Player Compare, and Trade Analyzer already read — see that
 * endpoint's comment in src/lib/api.ts calling this out as the shape "a
 * future Players/Player Detail page should reuse"). Nothing here re-derives
 * score, rank, or OVR.
 *
 * Filter semantics (age buckets, status, availability-by-health) are ported
 * from mobile's named reference implementation, mobile/src/screens/
 * PlayersScreen.tsx (matchesAge/matchesStatus/matchesAvailability) — not
 * from modules/player_asset_explorer_ui.py's desktop buckets, which use a
 * different age scheme (Under 23/23-25/26-28/29+) and an "Availability"
 * filter that means rostered-vs-unrostered-in-this-league rather than
 * health. Those are a genuinely different taxonomy (rostered/unrostered
 * needs a league roster map the rankings endpoint doesn't carry), so this
 * follows mobile's simpler, already-shipped health-based meaning rather
 * than force a shared filter that would silently change what the control
 * means on one client. Position options add "K" to mobile's QB/RB/WR/TE
 * list, matching this app's own existing convention for a position filter
 * (WaiversContent.tsx's FILTER_POSITIONS) and the real player pool, which
 * does include kickers.
 */

import type { RankedPlayer } from "./api";

export const PLAYERS_POSITION_FILTERS = ["ALL", "QB", "RB", "WR", "TE", "K"] as const;
export const PLAYERS_AGE_FILTERS = ["ALL", "Under 25", "25-28", "29+"] as const;
export const PLAYERS_STATUS_FILTERS = ["ALL", "Active", "Inactive"] as const;
export const PLAYERS_AVAILABILITY_FILTERS = ["ALL", "Healthy", "Injured"] as const;

export type PlayersAgeFilter = (typeof PLAYERS_AGE_FILTERS)[number];
export type PlayersStatusFilter = (typeof PLAYERS_STATUS_FILTERS)[number];
export type PlayersAvailabilityFilter = (typeof PLAYERS_AVAILABILITY_FILTERS)[number];

export function matchesPlayersAge(age: number | null, filter: PlayersAgeFilter): boolean {
  if (filter === "ALL") return true;
  if (age == null) return false;
  if (filter === "Under 25") return age < 25;
  if (filter === "25-28") return age >= 25 && age <= 28;
  return age >= 29;
}

export function matchesPlayersStatus(status: string | null, filter: PlayersStatusFilter): boolean {
  if (filter === "ALL") return true;
  const normalized = (status ?? "").trim().toLowerCase();
  return filter === "Active" ? normalized === "active" : normalized !== "active" && normalized !== "";
}

export function matchesPlayersAvailability(
  injuryStatus: string | null,
  filter: PlayersAvailabilityFilter,
): boolean {
  if (filter === "ALL") return true;
  const hasInjury = Boolean((injuryStatus ?? "").trim());
  return filter === "Injured" ? hasInjury : !hasInjury;
}

export interface PlayersFilterState {
  search: string;
  position: string;
  ageFilter: PlayersAgeFilter;
  statusFilter: PlayersStatusFilter;
  availabilityFilter: PlayersAvailabilityFilter;
}

/** Applies every control at once, preserving the server's existing
 * score-descending order (GET .../rankings already sorts — this never
 * re-sorts, same "keep the existing ... ordering" contract
 * player_asset_explorer_ui.filter_player_results documents on the desktop
 * side). */
export function filterPlayers(players: RankedPlayer[], filters: PlayersFilterState): RankedPlayer[] {
  const query = filters.search.trim().toLowerCase();
  return players
    .filter((p) => filters.position === "ALL" || p.position === filters.position)
    .filter((p) => matchesPlayersAge(p.age, filters.ageFilter))
    .filter((p) => matchesPlayersStatus(p.status, filters.statusFilter))
    .filter((p) => matchesPlayersAvailability(p.injury_status, filters.availabilityFilter))
    .filter((p) => !query || (p.name ?? "").toLowerCase().includes(query));
}
