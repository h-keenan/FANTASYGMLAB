/**
 * Fixtures for the no-signup /try/start-sit and /try/waivers pages. They feed the REAL MatchupContent "Suggested
 * Moves" module and the REAL WaiversContent board the same shapes the API returns, with the fictional players of the
 * sample league (lib/sampleLeague.ts). Fictional names, made-up numbers, always labelled "example league" on the page.
 */

import { formatMoney, formatMoneyRange } from "@/lib/money";
import type { MatchupResponse, MatchupSuggestedMove, WaiverPlayer, WaiverPriorityAdd, WaiversResponse } from "@/lib/api";

export const TRY_LEAGUE_NAME = "Sample Dynasty League";

const START_SIT_MOVE: MatchupSuggestedMove = {
  slot: "FLEX",
  start: {
    player_id: "sample-wr-taylor",
    name: "Taylor Exampleton",
    position: "WR",
    team: "DEN",
    tier: "starter",
    slot: "FLEX",
    points: 14.6,
    projection_status: "ok",
    injury_label: "",
  },
  over: {
    player_id: "sample-rb-casey",
    name: "Casey Placeholder",
    position: "RB",
    team: "NYG",
    tier: "starter",
    slot: "FLEX",
    points: 10.9,
    projection_status: "ok",
    injury_label: "",
  },
  over_reason: null,
  gain: 3.7,
  locked: false,
  range: {
    start: { name: "Taylor Exampleton", projected: 14.6, low: 8.8, high: 22.4 },
    over: { name: "Casey Placeholder", projected: 10.9, low: 6.1, high: 17.2 },
    stance: { kind: "toss_up", win_pct: 51 },
    lean: {
      kind: "ceiling",
      favors: "start",
      why: "Your matchup is close to a toss-up, so the higher ceiling is worth more than the slightly safer floor.",
    },
  },
};

/** A matchup payload carrying only what the Suggested Moves module reads. */
export const SAMPLE_START_SIT_MATCHUP: MatchupResponse = {
  ok: true,
  week: null,
  my_team: null,
  opponent: null,
  comparison: null,
  real_comparison: null,
  win_probability: null,
  suggested_moves: [START_SIT_MOVE],
  basis: "season_value",
  basis_label: "Projected points",
  reason: "",
};

export function waiverPlayer(overrides: Partial<WaiverPlayer> & Pick<WaiverPlayer, "player_id" | "name" | "position">): WaiverPlayer {
  return {
    team: "KC",
    age: 24,
    status: "Active",
    injury_status: null,
    tier: "backup",
    opportunity_label: "Backup With Upside",
    score: 1100,
    position_rank: 8,
    overall_rank: 70,
    stale_free_agent: false,
    injury_replacement_fit: false,
    injury_replacement_note: "",
    sleeper_trending_add: false,
    sleeper_trending_add_count: null,
    sleeper_trending_add_rank: null,
    opponent: null,
    opponent_is_home: null,
    opponent_defense_tier: null,
    overall_rating: 66,
    ...overrides,
  };
}

export function bid(low: number, high: number): WaiverPriorityAdd["faab"] {
  return { low_bid: low, high_bid: high, pct_low: low, pct_high: high, remaining: 100, dollars_known: true, label: `${formatMoneyRange(low, high)} of ${formatMoney(100)} remaining` };
}

export function priorityAdd(base: WaiverPlayer, overrides: Partial<WaiverPriorityAdd>): WaiverPriorityAdd {
  return {
    ...base,
    recommendation_label: "Add",
    recommendation_tone: "opportunity",
    faab: bid(8, 14),
    confidence_label: "High",
    confidence_reason: "Fills a real need on this roster.",
    ...overrides,
  };
}

const ADD_ONE = waiverPlayer({
  player_id: "sample-wr-reese",
  name: "Reese Wirewell",
  position: "WR",
  team: "CIN",
  tier: "starter",
  opportunity_label: "Starter Role Opening",
  score: 1480,
  position_rank: 4,
  overall_rank: 41,
  injury_replacement_fit: true,
  injury_replacement_note: "Next man up after a same-team starter was ruled out.",
  sleeper_trending_add: true,
  sleeper_trending_add_count: 5400,
  sleeper_trending_add_rank: 3,
  overall_rating: 74,
});
const ADD_TWO = waiverPlayer({
  player_id: "sample-rb-jamie",
  name: "Jamie Handcuffton",
  position: "RB",
  team: "SF",
  score: 1210,
  position_rank: 9,
  overall_rank: 88,
  opportunity_label: "Handcuff Value",
});

export const SAMPLE_WAIVERS: WaiversResponse = {
  ok: true,
  reason: "",
  players: [ADD_ONE, ADD_TWO],
  priority_adds: [
    priorityAdd(ADD_ONE, {
      recommendation_reason:
        "Fills your WR3 hole (8th of 12 in the league), a starter on his team is out, and he is only 12% rostered: the upgrade is large and the price is small.",
      injury_cover_for: "your injured starter",
      faab: bid(9, 15),
    }),
    priorityAdd(ADD_TWO, {
      recommendation_label: "Stash",
      recommendation_tone: "neutral",
      confidence_label: "Medium",
      confidence_reason: "Protects a dynasty asset you could not replace from the wire.",
      recommendation_reason: "Handcuff to your Riley Demoway: low cost, and it protects the most valuable back you own.",
      faab: bid(2, 4),
    }),
  ],
  needed_positions: ["WR", "RB"],
  available_count: 38,
  avg_wire_score: 640,
  injured_starters: 1,
  injury_positions: ["WR"],
  faab_remaining: 100,
  faab_initial: 100,
  faab_enabled: true,
  stash_candidates: [],
  watchlist_candidates: [],
  faab_targets: [],
  entitlement: { is_premium: true },
};
