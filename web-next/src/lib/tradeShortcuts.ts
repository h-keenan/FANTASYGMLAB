/**
 * "Add to Trade" / "Find trades" availability, the web twin of
 * mobile/src/lib/tradeShortcuts.ts (same semantics, same names). Pure, so the
 * Player Quick View's shared actions row and tests share one rule: shortcuts
 * only show when league ownership is KNOWN, never on a guess.
 */

export interface RosterOwnership {
  /** Player ids on the signed-in user's own roster in this league. */
  myPlayerIds: Set<string>;
  /** Player ids on any roster in this league (the user's own included). */
  rosteredPlayerIds: Set<string>;
  /** roster_id of the roster each rostered player sits on (the user's own included). */
  rosterIdByPlayerId?: Map<string, string>;
}

export interface TradeShortcutAvailability {
  /** Player is on some roster, so the Analyzer has a side to file them on. */
  canAddToTrade: boolean;
  /** Player is on the user's own roster (Trade Finder only shops your own). */
  canFindTrades: boolean;
}

const NONE: TradeShortcutAvailability = { canAddToTrade: false, canFindTrades: false };

export function tradeShortcutsFor(
  playerId: string | null | undefined,
  ownership: RosterOwnership | null,
): TradeShortcutAvailability {
  const id = String(playerId ?? "");
  if (!id || !ownership) return NONE;
  const mine = ownership.myPlayerIds.has(id);
  return { canAddToTrade: mine || ownership.rosteredPlayerIds.has(id), canFindTrades: mine };
}

/** Build ownership sets from the raw /my-roster and /rosters payloads. */
export function rosterOwnershipFrom(
  myRoster: Record<string, unknown> | null | undefined,
  rosters: Array<Record<string, unknown>>,
): RosterOwnership {
  const toIds = (value: unknown): string[] => (Array.isArray(value) ? value.map(String) : []);
  const myPlayerIds = new Set(toIds(myRoster?.players));
  const rosteredPlayerIds = new Set<string>(myPlayerIds);
  const rosterIdByPlayerId = new Map<string, string>();
  const myRosterId = myRoster?.roster_id;
  if (myRosterId !== undefined && myRosterId !== null) {
    for (const id of myPlayerIds) rosterIdByPlayerId.set(id, String(myRosterId));
  }
  for (const roster of rosters) {
    const rosterId = roster.roster_id;
    for (const id of toIds(roster.players)) {
      rosteredPlayerIds.add(id);
      if (rosterId !== undefined && rosterId !== null) rosterIdByPlayerId.set(id, String(rosterId));
    }
  }
  return { myPlayerIds, rosteredPlayerIds, rosterIdByPlayerId };
}

export type PlayerLeagueStatus =
  | { kind: "mine" }
  | { kind: "free_agent" }
  | { kind: "rostered"; teamName: string | null };

/**
 * Where a player sits in this league. Null until ownership is KNOWN (never a
 * guess), so a player is only called a free agent when every roster has been
 * read and none holds him. `teamNameByRosterId` is optional: without it a
 * rostered player is still reported, just without a team name.
 */
export function playerLeagueStatus(
  playerId: string | null | undefined,
  ownership: RosterOwnership | null,
  teamNameByRosterId?: Record<string, string> | null,
): PlayerLeagueStatus | null {
  const id = String(playerId ?? "");
  if (!id || !ownership) return null;
  if (ownership.myPlayerIds.has(id)) return { kind: "mine" };
  if (!ownership.rosteredPlayerIds.has(id)) return { kind: "free_agent" };
  const rosterId = ownership.rosterIdByPlayerId?.get(id);
  const name = rosterId ? teamNameByRosterId?.[rosterId] : undefined;
  return { kind: "rostered", teamName: name ? name : null };
}

export function playerLeagueStatusLabel(status: PlayerLeagueStatus): string {
  if (status.kind === "mine") return "On your roster";
  if (status.kind === "free_agent") return "Free agent";
  return status.teamName ? `On ${status.teamName}` : "On another team";
}
