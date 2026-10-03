import type { RankedPlayer, WaiverPlayer } from './api';

/**
 * Adapts a free-agent/waiver player into the RankedPlayer stub shape
 * PlayerDetail needs to fetch everything else itself — shared by
 * WaiversScreen's own rows and League Overview's compact Waiver
 * Suggestions section so both navigate to PlayerDetail the exact same way
 * instead of two slightly different inline conversions.
 */
export function rankedPlayerFromWaiverPlayer(player: WaiverPlayer): RankedPlayer {
  return {
    player_id: player.player_id,
    name: player.name,
    position: player.position,
    team: player.team,
    age: player.age,
    status: player.status,
    injury_status: player.injury_status,
    tier: player.tier,
    score: player.score,
    overall_rank: null,
    position_rank: null,
    rank_unavailable_reason: null,
    opportunity_label: null,
  };
}
