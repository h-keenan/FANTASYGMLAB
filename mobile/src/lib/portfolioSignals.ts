/**
 * Pure presentation decisions for a Portfolio league's signal rows, mirroring
 * web-next's BriefingItemPlayers / PortfolioContent.SignalRow so both
 * surfaces agree on which player identities a signal shows. No React imports
 * so `npm test` can run it directly.
 */

export interface SignalPlayer {
  player_id: string;
  name: string;
  position: string;
  team: string;
  tier: string;
  injury_status: string;
  score: number | null;
}

interface SignalItemShape {
  category?: string;
  headline?: string;
  reason?: string;
  route_player_id?: string;
  route_player_name?: string;
  route_player_position?: string;
  route_player_team?: string;
  route_player_tier?: string;
  route_player_score?: number | null;
  route_player_injury_status?: string;
  mentioned_players?: Array<{
    player_id: string;
    name: string;
    position: string;
    team: string;
    player_tier: string;
    injury_status?: string;
  }>;
  presentation?: { trade_package?: { send: unknown[]; receive: unknown[] } } | null;
}

export function hasTradePackage(item: SignalItemShape): boolean {
  const pkg = item.presentation?.trade_package;
  return Boolean(pkg && (pkg.send.length > 0 || pkg.receive.length > 0));
}

/** The route player first (when it resolves), then every other mentioned
 * player, never the same player twice. Empty for a trade-package item. */
export function signalPlayers(item: SignalItemShape): SignalPlayer[] {
  if (hasTradePackage(item)) return [];
  const players: SignalPlayer[] = [];
  if (item.route_player_id && item.route_player_name) {
    players.push({
      player_id: item.route_player_id,
      name: item.route_player_name,
      position: item.route_player_position ?? '',
      team: item.route_player_team ?? '',
      tier: item.route_player_tier ?? '',
      injury_status: item.route_player_injury_status ?? '',
      score: item.route_player_score ?? null,
    });
  }
  for (const player of item.mentioned_players ?? []) {
    if (player.player_id === item.route_player_id) continue;
    players.push({
      player_id: player.player_id,
      name: player.name,
      position: player.position,
      team: player.team,
      tier: player.player_tier,
      injury_status: player.injury_status ?? '',
      score: null,
    });
  }
  return players;
}

/** Same dedup as web: hide `reason` when it repeats the headline, and for a
 * Watch item with player identities showing, hide the pipe/dash-delimited
 * identity dump the player rows already render. */
export function showSignalReason(item: SignalItemShape): boolean {
  const reason = item.reason ?? '';
  if (!reason || reason === (item.headline ?? '')) return false;
  const hasVisual = hasTradePackage(item) || signalPlayers(item).length > 0;
  return !(item.category === 'watch' && hasVisual && (reason.includes(' | ') || reason.includes(' - ')));
}

/** Record + rank metadata line; the rank text is omitted for a top-3 league
 * because the gold rank badge already says it (same as web). */
export function portfolioMetadata(
  record: string,
  rank: number | null,
  tied: boolean,
): { showRankBadge: boolean; metadata: string; rankText: string } {
  const rankText = rank == null ? '' : tied ? `T-${rank}` : `#${rank}`;
  const showRankBadge = rank != null && rank <= 3;
  const metadata = [record, showRankBadge || !rankText ? '' : `Roster Power ${rankText}`].filter(Boolean).join(' · ');
  return { showRankBadge, metadata, rankText };
}
