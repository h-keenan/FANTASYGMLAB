import { describe, expect, it } from "vitest";

import type { LiveDraftRankingRow, LiveDraftTeamRow } from "./api";
import {
  diffRankMovement,
  diffTeamRankMovement,
  filterLiveDraftRankings,
  formatLiveDraftScore,
  liveDraftRankFilterOptions,
  movementGlyph,
  ranksById,
  teamRanksById,
} from "./liveDraftPresentation";

function rankingRow(overrides: Partial<LiveDraftRankingRow>): LiveDraftRankingRow {
  return {
    player_id: "p1",
    name: "Test Player",
    position: "WR",
    team: "SF",
    age: 24,
    tier: "Starter",
    is_rookie: false,
    overall_rank: 5,
    position_rank: 2,
    canonical_overall_rank: 5,
    canonical_position_rank: 2,
    rank_scoring_format: "",
    rank_unavailable_reason: "",
    base_value: 100,
    format_adjustment: 0,
    scarcity_score: 0,
    roster_fit_score: 0,
    age_strategy_adjustment: 0,
    availability_adjustment: 0,
    league_adjusted_draft_score: 105,
    overall_rating: 80,
    movement: 0,
    recommendation_label: "",
    recommendation_reason: "",
    ...overrides,
  };
}

function teamRow(overrides: Partial<LiveDraftTeamRow>): LiveDraftTeamRow {
  return {
    roster_id: 1,
    team_name: "Test Team",
    is_mine: false,
    team_rank: 1,
    movement: 0,
    trend_label: "",
    live_team_score: 80,
    roster_count: 10,
    pick_count: 2,
    positions: "WR 2",
    top_player: "Test Player",
    starter_value: 500,
    total_value: 700,
    ...overrides,
  };
}

describe("liveDraftRankFilterOptions", () => {
  it("omits Veterans when every available player is a rookie", () => {
    const rows = [rankingRow({ is_rookie: true })];
    expect(liveDraftRankFilterOptions(rows)).toEqual(["Overall", "QB", "RB", "WR", "TE", "Rookies"]);
  });

  it("adds Veterans once at least one non-rookie is on the board", () => {
    const rows = [rankingRow({ is_rookie: true }), rankingRow({ player_id: "p2", is_rookie: false })];
    expect(liveDraftRankFilterOptions(rows)).toEqual([
      "Overall",
      "QB",
      "RB",
      "WR",
      "TE",
      "Rookies",
      "Veterans",
    ]);
  });
});

describe("filterLiveDraftRankings", () => {
  const rows = [
    rankingRow({ player_id: "qb1", position: "QB", is_rookie: false }),
    rankingRow({ player_id: "wr1", position: "WR", is_rookie: true }),
    rankingRow({ player_id: "wr2", position: "WR", is_rookie: false }),
  ];

  it("returns everything for Overall", () => {
    expect(filterLiveDraftRankings(rows, "Overall")).toHaveLength(3);
  });

  it("filters by position", () => {
    expect(filterLiveDraftRankings(rows, "WR").map((r) => r.player_id)).toEqual(["wr1", "wr2"]);
  });

  it("filters Rookies and Veterans", () => {
    expect(filterLiveDraftRankings(rows, "Rookies").map((r) => r.player_id)).toEqual(["wr1"]);
    expect(filterLiveDraftRankings(rows, "Veterans").map((r) => r.player_id)).toEqual(["qb1", "wr2"]);
  });
});

describe("rank movement diffing", () => {
  it("computes previous_rank - current_rank, positive when a player climbs", () => {
    const current = [{ player_id: "p1", overall_rank: 3 }];
    const movement = diffRankMovement(current, { p1: 10 });
    expect(movement.p1).toBe(7);
  });

  it("computes a negative delta when a player slides down the board", () => {
    const current = [{ player_id: "p1", overall_rank: 10 }];
    const movement = diffRankMovement(current, { p1: 3 });
    expect(movement.p1).toBe(-7);
  });

  it("omits a player with no previous rank to diff against", () => {
    const current = [{ player_id: "p1", overall_rank: 3 }];
    expect(diffRankMovement(current, {})).toEqual({});
  });

  it("round-trips through ranksById for the next poll", () => {
    const rows = [rankingRow({ player_id: "p1", overall_rank: 4 }), rankingRow({ player_id: "p2", overall_rank: 9 })];
    expect(ranksById(rows)).toEqual({ p1: 4, p2: 9 });
  });
});

describe("team rank movement diffing", () => {
  it("computes previous_rank - current_rank keyed by roster_id", () => {
    const current = [teamRow({ roster_id: 2, team_rank: 1 })];
    const movement = diffTeamRankMovement(current, { "2": 4 });
    expect(movement["2"]).toBe(3);
  });

  it("round-trips through teamRanksById", () => {
    const rows = [teamRow({ roster_id: 1, team_rank: 2 }), teamRow({ roster_id: 2, team_rank: 1 })];
    expect(teamRanksById(rows)).toEqual({ "1": 2, "2": 1 });
  });
});

describe("movementGlyph", () => {
  it("shows an up triangle at +2 or more", () => {
    expect(movementGlyph(2)).toBe("▲ 2");
    expect(movementGlyph(9)).toBe("▲ 9");
  });

  it("shows a down triangle at -2 or more", () => {
    expect(movementGlyph(-2)).toBe("▼ 2");
    expect(movementGlyph(-9)).toBe("▼ 9");
  });

  it("shows a dash for anything inside the +/-1 deadband, or undefined", () => {
    expect(movementGlyph(1)).toBe("—");
    expect(movementGlyph(0)).toBe("—");
    expect(movementGlyph(-1)).toBe("—");
    expect(movementGlyph(undefined)).toBe("—");
  });
});

describe("formatLiveDraftScore", () => {
  it("formats to one decimal place", () => {
    expect(formatLiveDraftScore(105)).toBe("105.0");
    expect(formatLiveDraftScore(105.26)).toBe("105.3");
  });

  it("falls back to 0.0 for null/undefined/NaN", () => {
    expect(formatLiveDraftScore(null)).toBe("0.0");
    expect(formatLiveDraftScore(undefined)).toBe("0.0");
    expect(formatLiveDraftScore(NaN)).toBe("0.0");
  });
});
