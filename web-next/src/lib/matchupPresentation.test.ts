import { describe, expect, it } from "vitest";

import type { MatchupPositionEdge, MatchupRealStarter, MatchupResponse, MatchupSuggestedMove } from "./api";
import {
  edgeExplanation,
  formatSigned,
  lineupComparisonRows,
  lineupPlayerPoints,
  matchupVerdict,
  moveOverLine,
  moveSlotLabel,
  slotDisplayLabel,
} from "./matchupPresentation";

function edge(position: string, value: number, myCount = 1): MatchupPositionEdge {
  return {
    position,
    my_points: 10 + value,
    opponent_points: 10,
    edge: value,
    my_count: myCount,
    opponent_count: myCount,
    unmodeled: 0,
  };
}

function real(overrides: Partial<MatchupRealStarter>): MatchupRealStarter {
  return {
    player_id: "p",
    name: "Player",
    position: "RB",
    team: "SF",
    age: 25,
    status: "Active",
    injury_status: null,
    injury_label: "",
    tier: null,
    score: null,
    opportunity_label: null,
    overall_rating: null,
    actual_points: 0,
    projection: { status: "ok", point_estimate: 9.5, low: 7, high: 12, confidence: "medium", opponent: "SEA" },
    game_started: false,
    slot: "RB",
    ...overrides,
  };
}

function baseResponse(overrides: Partial<MatchupResponse>): MatchupResponse {
  return {
    ok: true,
    week: 7,
    my_team: null,
    opponent: null,
    comparison: null,
    real_comparison: null,
    win_probability: null,
    basis: "season_value",
    basis_label: "",
    reason: "",
    ...overrides,
  };
}

describe("formatSigned / slotDisplayLabel", () => {
  it("signs and rounds to one decimal", () => {
    expect(formatSigned(12.44)).toBe("+12.4");
    expect(formatSigned(-8.2)).toBe("-8.2");
    expect(formatSigned(0.01)).toBe("0.0");
  });

  it("compacts long slot names", () => {
    expect(slotDisplayLabel("SUPER_FLEX")).toBe("SF");
    expect(slotDisplayLabel("WR/RB")).toBe("W/R");
    expect(slotDisplayLabel("FLEX")).toBe("FLEX");
  });
});

describe("edgeExplanation (position edges)", () => {
  it("names the top strengths and weaknesses with their real numbers", () => {
    expect(edgeExplanation([edge("WR", 12.4, 3), edge("TE", 4.8), edge("QB", -2.1), edge("RB", -8.2, 2)])).toBe(
      "Your WRs (+12.4) and TE (+4.8) give you an edge, but your RBs (-8.2) and QB (-2.1) could be a problem.",
    );
  });

  it("uses singular agreement for one single-starter strength", () => {
    expect(edgeExplanation([edge("QB", 3), edge("WR", 0.4, 3)])).toBe(
      "Your QB (+3.0) gives you an edge, and no position trails by more than a point.",
    );
  });

  it("covers weakness-only and level matchups", () => {
    expect(edgeExplanation([edge("RB", -5, 2)])).toBe(
      "Your opponent is stronger at RBs (-5.0), and no position gives you more than a point.",
    );
    expect(edgeExplanation([edge("RB", 0.5, 2), edge("WR", -0.9, 3)])).toBe(
      "Every position is within a point either way.",
    );
    expect(edgeExplanation([])).toBeNull();
    expect(edgeExplanation(null)).toBeNull();
  });
});

describe("matchupVerdict", () => {
  const odds = (probability: number) => ({
    available: true,
    probability,
    my_projected_total: 100,
    opponent_projected_total: 90,
    coverage: { my: 1, opponent: 1 },
  });

  it("pre-game uses the win probability", () => {
    expect(matchupVerdict(baseResponse({ win_probability: odds(0.64), game_state: "pregame" })).headline).toBe(
      "You're favored to win.",
    );
    expect(matchupVerdict(baseResponse({ win_probability: odds(0.3) })).tone).toBe("risk");
    expect(matchupVerdict(baseResponse({ win_probability: odds(0.52) })).headline).toBe("Too close to call.");
  });

  it("live says on track; final reads the real result", () => {
    expect(matchupVerdict(baseResponse({ win_probability: odds(0.8), game_state: "live" })).headline).toBe(
      "You're on track to win.",
    );
    const final = baseResponse({
      game_state: "final",
      win_probability: odds(0),
      real_comparison: {
        my_points: 90,
        opponent_points: 100,
        margin: -10,
        edge: "opponent",
        basis: "sleeper_actual_lineup",
        basis_label: "",
      },
    });
    expect(matchupVerdict(final)).toEqual({ headline: "You lost this week.", tone: "risk" });
  });

  it("is honest with no probability", () => {
    expect(matchupVerdict(baseResponse({ win_probability: { available: false, reason: "no_starters" } })).headline).toBe(
      "Not enough projections yet to call it.",
    );
  });
});

describe("lineupPlayerPoints", () => {
  it("projection before kickoff, real points after, bye noted", () => {
    expect(lineupPlayerPoints(real({}))).toEqual({ value: 9.5, kind: "proj", note: null });
    expect(lineupPlayerPoints(real({ game_started: true, actual_points: 3.2 }))).toEqual({
      value: 3.2,
      kind: "pts",
      note: null,
    });
    expect(
      lineupPlayerPoints(
        real({ projection: { status: "bye_week", point_estimate: null, low: null, high: null, confidence: null, opponent: null } }),
      ),
    ).toEqual({ value: null, kind: null, note: "bye" });
  });
});

describe("lineupComparisonRows", () => {
  it("zips each slot group, keeps empty slots, and leaves unmatched cells null", () => {
    const mine = [
      real({ player_id: "q", slot: "QB" }),
      real({ player_id: "r1", slot: "RB" }),
      real({ player_id: "r2", slot: "RB" }),
      real({ player_id: "d", slot: "DEF" }),
    ];
    const theirs = [real({ player_id: "oq", slot: "QB" }), real({ player_id: "or1", slot: "RB" })];
    const rows = lineupComparisonRows(mine, theirs, [], ["RB"]);

    expect(rows.map((row) => row.slot)).toEqual(["QB", "RB", "RB", "DEF"]);
    expect(rows[1].opponent).not.toBe("empty");
    expect(rows[2].opponent).toBe("empty");
    expect(rows[3].opponent).toBeNull();
  });
});

describe("suggested moves (suggested vs actual diff)", () => {
  const move: MatchupSuggestedMove = {
    slot: "FLEX",
    start: {
      player_id: "x",
      name: "Chris Godwin Jr.",
      position: "WR",
      team: "TB",
      tier: null,
      slot: "FLEX",
      points: 6.3,
      projection_status: "ok",
      injury_label: "",
    },
    over: {
      player_id: "y",
      name: "Makai Leni",
      position: "WR",
      team: "JAX",
      tier: null,
      slot: "FLEX",
      points: 4.7,
      projection_status: "ok",
      injury_label: "",
    },
    over_reason: null,
    gain: 1.6,
    locked: false,
  };

  it("labels the over line by reason", () => {
    expect(moveOverLine(move)).toBe("Over Makai Leni (Proj 4.7)");
    expect(moveOverLine({ ...move, over_reason: "bye_week" })).toBe("Over Makai Leni (on bye)");
    expect(moveOverLine({ ...move, over_reason: "ruled_out", over: { ...move.over!, injury_label: "Out" } })).toBe(
      "Over Makai Leni (Out)",
    );
    expect(moveOverLine({ ...move, over: null, over_reason: "empty_slot" })).toBe("Fills your empty FLEX slot");
  });

  it("adds a slot ordinal only when the lineup has several of that slot", () => {
    const actual = [real({ player_id: "y", slot: "FLEX" })];
    expect(moveSlotLabel(move, actual)).toBe("FLEX");
    const rbMove = { ...move, slot: "RB", over: { ...move.over!, player_id: "r2" } };
    const rbs = [real({ player_id: "r1", slot: "RB" }), real({ player_id: "r2", slot: "RB" })];
    expect(moveSlotLabel(rbMove, rbs)).toBe("RB2");
  });
});
