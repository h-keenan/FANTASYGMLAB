import { describe, expect, it } from "vitest";

import {
  formatDelta,
  formatOdds,
  gamesReasonAction,
  gamesReasonMessage,
  recordLabel,
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
