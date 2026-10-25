import type { BriefingItem, DashboardResponse, LeagueTeamRankingsResponse, TeamRanking } from "@/lib/api";
import {
  SAMPLE_DASHBOARD_ITEMS,
  SAMPLE_DASHBOARD_WEEK,
  SAMPLE_PULSE_TEAMS,
  SAMPLE_SNAPSHOT,
  SAMPLE_THIS_WEEK_ROWS,
} from "@/lib/sampleLeague";

/**
 * Maps the static fictional sample data (lib/sampleLeague.ts) onto the real
 * Dashboard API shapes, so the real DashboardContent modules render it
 * unchanged. Pure and synchronous: no fetch, no storage, no analytics.
 * Mobile twin: mobile/src/lib/sampleDashboard.ts.
 */

/** Stand-in league id. Never sent anywhere: links are blocked in sample mode. */
export const SAMPLE_DASHBOARD_LEAGUE_ID = "sample";

export function sampleBriefingItems(): BriefingItem[] {
  return SAMPLE_DASHBOARD_ITEMS.map((item, index) => ({
    category: item.category,
    headline: item.headline,
    reason: item.reason,
    supporting_context: null,
    destination: item.destination,
    route_player_id: "",
    route_player_name: "",
    route_player_position: "",
    route_player_team: "",
    route_player_tier: "",
    route_player_score: null,
    route_player_injury_status: "",
    mentioned_players: [],
    recommendation_narrative: null,
    presentation: null,
    recommendation_id: `sample-${index}`,
    tier_label: item.tier_label,
  }));
}

export function sampleDashboardResponse(): DashboardResponse {
  const items = sampleBriefingItems();
  return {
    ok: true,
    this_week: {
      mode: "in_season",
      week: SAMPLE_DASHBOARD_WEEK,
      next_action: null,
      rows: SAMPLE_THIS_WEEK_ROWS.map((row) => ({ ...row, player_id: "" })),
    },
    items,
    quiet: false,
    quiet_reason: "",
    team_snapshot: {
      wins: SAMPLE_SNAPSHOT.wins,
      losses: SAMPLE_SNAPSHOT.losses,
      ties: 0,
      health_flag: "Stable",
      key_injuries_summary: "",
      top_injury_impact_summary: "",
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
    } as DashboardResponse["team_snapshot"],
    reason: "",
    // Free-limit / upsell copy is real-account state, so the sample shows none.
    entitlement: { is_premium: true, visible_count: items.length, hidden_count: 0 },
  };
}

export function sampleTeamRankings(): Promise<LeagueTeamRankingsResponse> {
  const teams = SAMPLE_PULSE_TEAMS.map(
    (team, index) =>
      ({
        roster_id: `sample-${index}`,
        team_name: team.team_name,
        avatar_url: null,
        transaction_activity_count: team.transaction_activity_count,
        current_streak: team.current_streak,
      }) as unknown as TeamRanking,
  );
  return Promise.resolve({
    ok: true,
    teams,
    reason: "",
    standings_available: false,
    standings_message: "",
    season: "",
    week_label: "",
    playoff_teams: null,
  });
}
