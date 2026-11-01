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
  for (const roster of rosters) {
    for (const id of toIds(roster.players)) rosteredPlayerIds.add(id);
  }
  return { myPlayerIds, rosteredPlayerIds };
}
