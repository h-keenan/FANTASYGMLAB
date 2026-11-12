import { describe, expect, it } from "vitest";

import { buildReviewShareModel, buildSimReviewSections, reviewDecisionCard, reviewSignedDelta } from "./simReview";

const player = { id: "1", name: "Jalen Coker", pos: "WR", team: "CAR", headshot_id: "1" };
const review = {
  season_stats: [{ key: "ppg", label: "Points per game", value: "97.5" }, { key: "high", label: "Best week", value: "168", tone: "good" }],
  awards: [
    { key: "best_trade", kind: "trade", tone: "good", label: "Best trade", headline: "Week 3 trade", players: [{ ...player, role: "get" }], delta: { value: 42.3, unit: "pts" }, detail: "d", outcome: "Won the deal" },
    { key: "injury_cost", kind: "injury", tone: "bad", label: "Injury", headline: "Missed 9 weeks", players: [player], delta: { value: -108, unit: "pts" } },
    { key: "best_pick", kind: "draft", tone: "good", label: "Best pick", headline: "Round 10", players: [player], delta: { value: -4, unit: "adp" } },
  ],
  injuries: { your_injuries: 3, weeks_missed: 9, points_lost: 108 },
  rank_journey: [{ week: 1, rank: 5, wins: 1, losses: 0 }, { week: 2, rank: 2, wins: 2, losses: 0 }],
  team_count: 12,
  champion_path: { name: "Team", seed: 1, total_rounds: 3, is_you: false, rounds: [{ round: 1, bye: true }, { round: 2, opponent: "X", opponent_seed: 5, pts: 100, opp_pts: 90, won: true }] },
  leaders: { league: [{ pos: "QB", rows: [{ player, pts: 300, ppg: 20, team_name: "T", is_you: true }] }], yours: [{ label: "Passing yards", rows: [{ player, value: 3000 }] }] },
  games: { closest_yours: [{ home: "A", away: "B", home_pts: 100, away_pts: 99.5, margin: 0.5, week: 4, kind: "regular", is_yours: true, you_won: true }], closest_league: [] },
};

describe("buildSimReviewSections", () => {
  it("returns nothing for a result with no review and no decisions", () => {
    expect(buildSimReviewSections({})).toEqual([]);
    expect(buildSimReviewSections({ review: "bad", decisions: 3 })).toEqual([]);
  });

  it("maps the backend review into typed sections with tones", () => {
    const sections = buildSimReviewSections({ review, decisions: [{ kind: "lineup", title: "Week 2: 49.9 points sat on your bench", detail: "x", players: [{ ...player, role: "bench" }], impact: { season_value: -0.8 } }] });
    const ids = sections.map((s) => s.id);
    expect(ids).toEqual(["stats", "decisions", "moves", "injuries", "champion-path", "journey", "leaders", "your-leaders", "closest-yours"]);
    const moves = sections.find((s) => s.id === "moves");
    expect(moves?.kind === "cards" && moves.cards[0].delta).toEqual({ text: "+42.3 pts", tone: "success" });
    expect(moves?.kind === "cards" && moves.cards[1].delta?.text).toBe("-4 vs ADP");
    const decisions = sections.find((s) => s.id === "decisions");
    expect(decisions?.kind === "cards" && decisions.cards[0]).toMatchObject({ glyph: "lineup", tone: "warning", delta: { text: "-49.9 pts", tone: "danger" } });
    const path = sections.find((s) => s.id === "champion-path");
    expect(path?.kind === "path" && path.steps.map((s) => s.label)).toEqual(["Round 1", "Semifinal"]);
  });

  it("skips malformed rows instead of throwing", () => {
    const sections = buildSimReviewSections({ review: { awards: [null, 3, { kind: "trade" }], leaders: { league: [{ rows: [{ player: null }] }] } } });
    expect(sections).toEqual([]);
  });

  it("formats signed deltas and share models", () => {
    expect(reviewSignedDelta(-3.04, "pts")).toEqual({ text: "-3 pts", tone: "danger" });
    expect(reviewDecisionCard({ title: "t" }, 0)?.glyph).toBe("trade");
    const model = buildReviewShareModel({ letter: "B", gradeTone: "accent", headline: "h", sections: buildSimReviewSections({ review }) });
    expect(model.highlights).toHaveLength(3);
    expect(model.stats[0]).toEqual({ label: "Points per game", value: "97.5" });
  });
});
