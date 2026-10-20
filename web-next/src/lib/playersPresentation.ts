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
 *
 * Revision 17 adds the rostered/available-in-this-league facet deliberately
 * deferred above (modules/player_asset_explorer_ui.py's
 * AVAILABILITY_FILTERS — "All availability"/"Rostered"/"Available" — which
 * needs a league-wide roster map the rankings endpoint never carried; that
 * map now comes from GET .../rosters, the same raw Sleeper passthrough
 * Trade Analyzer's roster-browse already reads). This is a genuinely
 * different facet from PLAYERS_AVAILABILITY_FILTERS above (that one means
 * health), so it gets its own name — PLAYERS_ROSTER_FILTERS — rather than
 * overloading "availability" with two meanings on one page.
 *
 * Revision 20 adds Madden-style stat sorting: sort by Value (the existing
 * default), OVR, or any position-relevant raw stat the rankings endpoint now
 * carries per player (modules.player_quick_view.rankings_stat_entries_for_row
 * — see RankedPlayer.stats in lib/api.ts), with a raw-value/percentile
 * toggle for the stat columns. This is the one place on this page that
 * re-sorts the server's existing score-descending order — see sortPlayers'
 * own docstring.
 */

import type { RankedPlayer, RankedPlayerStat } from "./api";

export const PLAYERS_POSITION_FILTERS = ["ALL", "QB", "RB", "WR", "TE", "K"] as const;
export const PLAYERS_AGE_FILTERS = ["ALL", "Under 25", "25-28", "29+"] as const;
export const PLAYERS_STATUS_FILTERS = ["ALL", "Active", "Inactive"] as const;
export const PLAYERS_AVAILABILITY_FILTERS = ["ALL", "Healthy", "Injured"] as const;
export const PLAYERS_ROSTER_FILTERS = ["ALL", "Rostered", "Available"] as const;

export type PlayersAgeFilter = (typeof PLAYERS_AGE_FILTERS)[number];
export type PlayersStatusFilter = (typeof PLAYERS_STATUS_FILTERS)[number];
export type PlayersAvailabilityFilter = (typeof PLAYERS_AVAILABILITY_FILTERS)[number];
export type PlayersRosterFilter = (typeof PLAYERS_ROSTER_FILTERS)[number];

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

/** Rostered-vs-available, league-wide — modules/player_asset_explorer_ui.py's
 * AVAILABILITY_FILTERS meaning, verbatim. `rosteredPlayerIds` is the union of
 * every roster's `players` array (GET .../rosters, raw Sleeper passthrough),
 * same source rostered_player_id_set builds from roster_player_map on the
 * desktop side — never re-derived from anything player-shaped. */
export function matchesPlayersRosterStatus(
  playerId: string,
  rosteredPlayerIds: Set<string>,
  filter: PlayersRosterFilter,
): boolean {
  if (filter === "ALL") return true;
  const isRostered = rosteredPlayerIds.has(playerId);
  return filter === "Rostered" ? isRostered : !isRostered;
}

export interface PlayersFilterState {
  search: string;
  position: string;
  ageFilter: PlayersAgeFilter;
  statusFilter: PlayersStatusFilter;
  availabilityFilter: PlayersAvailabilityFilter;
  rosterFilter?: PlayersRosterFilter;
  rosteredPlayerIds?: Set<string>;
}

/** Applies every control at once, preserving the server's existing
 * score-descending order (GET .../rankings already sorts — this never
 * re-sorts, same "keep the existing ... ordering" contract
 * player_asset_explorer_ui.filter_player_results documents on the desktop
 * side). `rosterFilter`/`rosteredPlayerIds` are optional so every existing
 * call site (and test) that doesn't know about roster ownership keeps
 * working unchanged — omitting them is equivalent to "ALL". */
export function filterPlayers(players: RankedPlayer[], filters: PlayersFilterState): RankedPlayer[] {
  const query = filters.search.trim().toLowerCase();
  const rosterFilter = filters.rosterFilter ?? "ALL";
  const rosteredPlayerIds = filters.rosteredPlayerIds ?? new Set<string>();
  return players
    .filter((p) => filters.position === "ALL" || p.position === filters.position)
    .filter((p) => matchesPlayersAge(p.age, filters.ageFilter))
    .filter((p) => matchesPlayersStatus(p.status, filters.statusFilter))
    .filter((p) => matchesPlayersAvailability(p.injury_status, filters.availabilityFilter))
    .filter((p) => matchesPlayersRosterStatus(p.player_id, rosteredPlayerIds, rosterFilter))
    .filter((p) => !query || (p.name ?? "").toLowerCase().includes(query));
}

/** The two always-present sort keys — not a stat entry, so neither has a
 * separate "percentile" number of its own (OVR already *is* one; Value has
 * no meaningful position-relative percentile distinct from the rank it
 * already shows). */
export const VALUE_SORT_KEY = "value";
export const OVERALL_RATING_SORT_KEY = "overall_rating";

export type PlayersSortMode = "raw" | "percentile";

export interface PlayersSortOption {
  key: string;
  label: string;
  /** False for Value/OVR — see the module comment above. True for every
   * stat-column option, which always carries a percentile field (possibly
   * `null` below PERCENTILE_MIN_POOL). */
  supportsPercentile: boolean;
}

/** Builds the Sort By dropdown's options from whatever stats are actually
 * present on `players` — e.g. filtering down to one position narrows this to
 * that position's curated stat set; "ALL" positions pools the union of
 * every stat any visible player carries. Never hand-rolls a second
 * per-position stat catalog — this just reflects back whatever
 * modules.player_quick_view.rankings_stat_entries_for_row already decided
 * was relevant server-side, in the order it returned them. */
export function buildPlayersSortOptions(players: RankedPlayer[]): PlayersSortOption[] {
  const seen = new Map<string, string>();
  for (const player of players) {
    for (const stat of player.stats ?? []) {
      if (!seen.has(stat.key)) seen.set(stat.key, stat.label);
    }
  }
  const statOptions: PlayersSortOption[] = Array.from(seen, ([key, label]) => ({
    key,
    label,
    supportsPercentile: true,
  }));
  return [
    { key: VALUE_SORT_KEY, label: "Value", supportsPercentile: false },
    { key: OVERALL_RATING_SORT_KEY, label: "OVR", supportsPercentile: false },
    ...statOptions,
  ];
}

export function findPlayersStat(player: RankedPlayer, key: string): RankedPlayerStat | undefined {
  return player.stats?.find((stat) => stat.key === key);
}

/** Sorts `players` descending by `sortKey` — Madden's "sort the board by any
 * column" convention, not the server's default score-descending order
 * (`filterPlayers` above deliberately never re-sorts; this is the one place
 * on this page that does, and only applied on top of it). `sortMode` picks
 * raw value vs. this stat's position-group percentile for a stat column
 * (ignored for Value/OVR — see PlayersSortOption.supportsPercentile).
 *
 * A player missing the sort column entirely (a stat not applicable to their
 * position, or `null` because their position's percentile pool was too
 * thin — see PERCENTILE_MIN_POOL) sorts to the bottom rather than
 * disappearing or crashing, the same fail-open spirit as every other
 * optional field already on this page. */
export function sortPlayers(
  players: RankedPlayer[],
  sortKey: string,
  sortMode: PlayersSortMode = "raw",
): RankedPlayer[] {
  function metric(player: RankedPlayer): number | null {
    if (sortKey === VALUE_SORT_KEY) return player.score ?? null;
    if (sortKey === OVERALL_RATING_SORT_KEY) return player.overall_rating ?? null;
    const stat = findPlayersStat(player, sortKey);
    if (!stat) return null;
    return sortMode === "percentile" ? stat.percentile : stat.value;
  }
  return [...players].sort((a, b) => {
    const av = metric(a);
    const bv = metric(b);
    if (av == null && bv == null) return 0;
    if (av == null) return 1;
    if (bv == null) return -1;
    return bv - av;
  });
}

/** Display text for one stat's raw value, format-aware — "share" stats are
 * already normalized to 0-100 by the server (see RankedPlayerStat in
 * lib/api.ts), everything else is just rounded to a sane precision. */
export function formatPlayersStatValue(stat: RankedPlayerStat): string {
  if (stat.format === "share") return `${Math.round(stat.value)}%`;
  if (stat.format === "rate" || stat.format === "ppg" || stat.format === "points") return stat.value.toFixed(1);
  return String(Math.round(stat.value));
}

/** "1st"/"2nd"/"3rd"/"4th"... for a 1-100 percentile — the 11th/12th/13th
 * exception first, then last-digit, matching
 * modules.player_quick_view._ordinal's own rule on the Python side. */
export function formatPlayersPercentile(percentile: number): string {
  const lastTwo = percentile % 100;
  if (lastTwo >= 10 && lastTwo <= 20) return `${percentile}th`;
  const suffix = { 1: "st", 2: "nd", 3: "rd" }[percentile % 10] ?? "th";
  return `${percentile}${suffix}`;
}
