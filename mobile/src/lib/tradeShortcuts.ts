/**
 * "Add to Trade" / "Find trades" player shortcuts (tap-depth audit 2026-10,
 * proposals #1 and #2) — pure, so they're covered by the node test runner
 * without rendering a screen.
 *
 * Mobile PlayerDetail and Players rows deep-link into the Trades host with
 * `Trades { initialTab: 'make' | 'search', tradePlayer }`. Trade Analyzer
 * ("Make a Trade") then files the player on the right side, selects the
 * owning team, and moves the active side to the still-empty one, so the
 * next tap picks the counter-asset. Trade Finder ("Search") pre-selects the
 * player and runs the search straight away.
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
  const id = String(playerId ?? '');
  if (!id || !ownership) return NONE;
  const mine = ownership.myPlayerIds.has(id);
  return {
    canAddToTrade: mine || ownership.rosteredPlayerIds.has(id),
    canFindTrades: mine,
  };
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
  | { kind: 'mine' }
  | { kind: 'free_agent' }
  | { kind: 'rostered'; teamName: string | null };

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
  const id = String(playerId ?? '');
  if (!id || !ownership) return null;
  if (ownership.myPlayerIds.has(id)) return { kind: 'mine' };
  if (!ownership.rosteredPlayerIds.has(id)) return { kind: 'free_agent' };
  const rosterId = ownership.rosterIdByPlayerId?.get(id);
  const name = rosterId ? teamNameByRosterId?.[rosterId] : undefined;
  return { kind: 'rostered', teamName: name ? name : null };
}

export function playerLeagueStatusLabel(status: PlayerLeagueStatus): string {
  if (status.kind === 'mine') return 'On your roster';
  if (status.kind === 'free_agent') return 'Free agent';
  return status.teamName ? `On ${status.teamName}` : 'On another team';
}

export type TradeSide = 'send' | 'receive';

export interface QuickAddPlacement {
  /** Side the player is filed on. */
  side: TradeSide;
  /** Owning team to select as the partner (receive side only). */
  partnerRosterId: string | null;
  /** Side to make active afterwards: the empty one. */
  focusSide: TradeSide;
}

/**
 * Where a quick-added player goes. Mirrors web TradeAnalyzerContent's
 * quickAddPlayerId: your own player -> "You send"; another team's ->
 * "You receive" with that team selected. Unlike web today, focus moves to
 * the opposite (empty) side. Null when the player isn't on any roster in
 * the league (fail open: nothing is added).
 */
export function quickAddPlacement(
  playerId: string,
  myPlayerIds: Set<string>,
  otherTeams: Array<{ rosterId: string; playerIds: Set<string> }>,
): QuickAddPlacement | null {
  if (!playerId) return null;
  if (myPlayerIds.has(playerId)) {
    return { side: 'send', partnerRosterId: null, focusSide: 'receive' };
  }
  const owner = otherTeams.find((team) => team.playerIds.has(playerId));
  if (!owner) return null;
  return { side: 'receive', partnerRosterId: owner.rosterId, focusSide: 'send' };
}

/**
 * True when the current route is the Trade Analyzer itself (the Trades host
 * on its "Make a Trade" tab), where "Add to Trade" on a quick view would be
 * redundant. The Trade Finder tab ("search") keeps it.
 */
export function isTradeAnalyzerRoute(routeName: string | null | undefined, initialTab?: string | null): boolean {
  return routeName === 'Trades' && initialTab !== 'search';
}
