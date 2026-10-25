import type { DashboardItem, TeamSnapshot, ThisWeek } from './api';
import type { PulseTeam } from './leaguePulse';
import {
  SAMPLE_DASHBOARD_ITEMS,
  SAMPLE_DASHBOARD_WEEK,
  SAMPLE_PULSE_TEAMS,
  SAMPLE_SNAPSHOT,
  SAMPLE_THIS_WEEK_ROWS,
} from './sampleLeague.ts';

/**
 * Maps the static fictional sample data (lib/sampleLeague.ts) onto the real
 * Dashboard API shapes so the real Dashboard modules render it unchanged.
 * Pure: no fetch, no storage, no analytics. Web twin:
 * web-next/src/lib/sampleDashboard.ts.
 */

/** Stand-in league id. Never sent anywhere: navigation is blocked in the sample. */
export const SAMPLE_DASHBOARD_LEAGUE_ID = 'sample';

export function sampleDashboardItems(): DashboardItem[] {
  return SAMPLE_DASHBOARD_ITEMS.map((item, index) => ({
    category: item.category,
    headline: item.headline,
    reason: item.reason,
    supporting_context: '',
    destination: item.destination,
    route_player_id: '',
    route_player_name: '',
    route_player_position: '',
    route_player_team: '',
    route_player_tier: '',
    route_player_score: null,
    route_player_injury_status: '',
    mentioned_players: [],
    recommendation_narrative: null,
    presentation: null,
    recommendation_id: `sample-${index}`,
    tier_label: item.tier_label,
  }));
}

export function sampleThisWeek(): ThisWeek {
  return {
    mode: 'in_season',
    week: SAMPLE_DASHBOARD_WEEK,
    next_action: null,
    rows: SAMPLE_THIS_WEEK_ROWS.map((row) => ({ ...row, player_id: '' })),
  };
}

export function sampleTeamSnapshot(): TeamSnapshot {
  return {
    wins: SAMPLE_SNAPSHOT.wins,
    losses: SAMPLE_SNAPSHOT.losses,
    ties: 0,
    health_flag: 'Stable',
    key_injuries_summary: '',
    top_injury_impact_summary: '',
    top_injury_impact_players: [],
    injured_starters: SAMPLE_SNAPSHOT.injuredStarters,
    average_age: SAMPLE_SNAPSHOT.averageAge,
    power_rank: SAMPLE_SNAPSHOT.powerRank,
    power_rank_tied: false,
    franchise_rank: SAMPLE_SNAPSHOT.franchiseRank,
    franchise_rank_tied: false,
    starter_rank: SAMPLE_SNAPSHOT.starterRank,
    starter_rank_tied: false,
    bench_rank: SAMPLE_SNAPSHOT.benchRank,
    bench_rank_tied: false,
  };
}

export function samplePulseTeams(): PulseTeam[] {
  return SAMPLE_PULSE_TEAMS.map((team) => ({ ...team, avatar_url: null }));
}
