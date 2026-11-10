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

/**
 * Adapts a server-search match (/players/search?available_only=true, the
 * /rankings row shape) into a WaiverPlayer row for the Waivers list. The
 * wire-only signals the search does not compute (matchup, trending, injury
 * fit) get neutral values, and wire-relative ranks are null rather than
 * passing off league-global ranks as wire ranks; OVR is already the same
 * league-pool percentile Waivers shows.
 */
export function waiverPlayerFromRankedPlayer(player: RankedPlayer): WaiverPlayer {
  return {
    player_id: player.player_id,
    name: player.name,
    position: player.position,
    team: player.team,
    age: player.age,
    status: player.status,
    injury_status: player.injury_status,
    tier: player.tier,
    opportunity_label: player.opportunity_label,
    score: player.score,
    position_rank: null,
    overall_rank: null,
    stale_free_agent: false,
    injury_replacement_fit: false,
    injury_replacement_note: '',
    sleeper_trending_add: false,
    sleeper_trending_add_count: null,
    sleeper_trending_add_rank: null,
    opponent: null,
    opponent_is_home: null,
    opponent_defense_tier: null,
    overall_rating: player.overall_rating ?? null,
  };
}
