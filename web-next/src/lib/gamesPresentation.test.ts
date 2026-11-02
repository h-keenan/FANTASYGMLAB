import { describe, expect, it } from "vitest";

import {
  formatDelta,
  formatOdds,
  gamesReasonAction,
  gamesReasonMessage,
  recordLabel,
  tradeOddsView,
  seedChangeLabel,
  whatIfSummary,
  whatIfTone,
  withPick,
} from "./gamesPresentation";

describe("gamesPresentation", () => {
  it("maps reasons to short messages and a next step", () => {
    expect(gamesReasonMessage("offseason")).toMatch(/regular season/);
    expect(gamesReasonMessage("something_new")).toMatch(/Not available/);
    expect(gamesReasonAction("no_sleeper_username_linked")).toBe("account");
    expect(gamesReasonAction("offseason")).toBe("dashboard");
  });

  it("formats odds and deltas", () => {
    expect(formatOdds(61.4)).toBe("61%");
    expect(formatOdds(null)).toBe("-");
    expect(formatDelta(4.23)).toBe("+4.2");
    expect(formatDelta(-1)).toBe("-1.0");
    expect(formatDelta(0.01)).toBe("0.0");
  });

  it("describes seed moves with lower numbers as better", () => {
    expect(seedChangeLabel(-2)).toBe("2 seeds higher");
    expect(seedChangeLabel(1)).toBe("1 seed lower");
    expect(seedChangeLabel(0)).toBe("Seed unchanged");
  });

  it("calls a change inside noise neutral instead of claiming an effect", () => {
    expect(whatIfTone({ playoff_probability: 1, within_noise: true })).toBe("neutral");
    expect(whatIfSummary({ playoff_probability: 1, within_noise: true })).toMatch(/noise/);
    expect(whatIfTone({ playoff_probability: 5, within_noise: false })).toBe("positive");
    expect(whatIfSummary({ playoff_probability: -5.5, within_noise: false })).toBe("Lowers your playoff odds by 5.5 points.");
  });

  it("applies an optimistic pick to one matchup only", () => {
    const next = withPick(
      [
        { matchup_id: "1", my_pick: null },
        { matchup_id: "2", my_pick: "3" },
      ],
      "1",
      "2",
    );
    expect(next).toEqual([
      { matchup_id: "1", my_pick: "2" },
      { matchup_id: "2", my_pick: "3" },
    ]);
  });

  it("shows a record from graded picks", () => {
    expect(recordLabel({ correct: 7, graded: 10 })).toBe("7-3");
    expect(recordLabel(undefined)).toBe("0-0");
  });
});

describe("tradeOddsView", () => {
  const base = {
    reason: "",
    baseline: { playoff_probability: 40, title_probability: 5 },
    scenario: { playoff_probability: 52, title_probability: 8 },
    change: { playoff_probability: 12, title_probability: 3, within_noise: false, title_within_noise: false },
    margin_points: 2.5,
    trials: 3000,
    slope_fitted: true,
    weeks_remaining: 6,
  };

  it("states the change with its margin and sample size", () => {
    const view = tradeOddsView(base)!;
    expect(view.tone).toBe("positive");
    expect(view.headline).toBe("Playoff odds 40% to 52% (+12.0 pts)");
    expect(view.titleLine).toBe("Title odds 5% to 8% (+3.0 pts)");
    expect(view.detail).toContain("3,000 simulated seasons");
    expect(view.detail).toContain("2.5");
    expect(view.notes).toEqual([]);
  });

  it("says no measurable change inside the margin and omits unavailable title odds", () => {
    const view = tradeOddsView({
      ...base,
      scenario: { playoff_probability: 41, title_probability: null },
      change: { playoff_probability: 1, title_probability: null, within_noise: true },
    })!;
    expect(view.tone).toBe("neutral");
    expect(view.headline).toContain("no measurable change");
    expect(view.titleLine).toBeNull();
  });

  it("flags excluded picks and an uncalibrated model, and returns null for any reason", () => {
    const view = tradeOddsView({ ...base, picks_excluded: true, slope_fitted: false })!;
    expect(view.notes).toHaveLength(2);
    expect(tradeOddsView({ ...base, reason: "no_games_left" })).toBeNull();
    expect(tradeOddsView(null)).toBeNull();
  });
});
