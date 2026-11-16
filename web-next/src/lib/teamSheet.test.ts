import { describe, expect, it } from "vitest";

import {
  teamSheetNextGameLine,
  teamSheetPositionLine,
  teamSheetSeasonLine,
  teamSheetStrengthNeedLine,
  teamSheetStreakTone,
  tradeStyleFromSignals,
} from "./teamSheet";

describe("teamSheet", () => {
  it("formats the position line and strengths/needs", () => {
    expect(teamSheetPositionLine({ rank: 3, teams: 12, depth: 2 })).toBe("#3 of 12 · depth 2");
    expect(teamSheetStrengthNeedLine(["RB", "WR"], ["TE"])).toBe("Strong at RB, WR. Needs TE.");
    expect(teamSheetStrengthNeedLine([], undefined)).toBe("");
  });

  it("formats next game, streak tone and seasons", () => {
    expect(teamSheetNextGameLine({ week: 13, opponent: "Rival" })).toBe("Week 13 vs Rival");
    expect(teamSheetNextGameLine(null)).toBe("");
    expect(teamSheetStreakTone("W12")).toBe("success");
    expect(teamSheetStreakTone("L2")).toBe("danger");
    expect(teamSheetSeasonLine({ wins: 9, losses: 3, ties: 0, place: 2, of: 12 })).toBe("9-3 · #2 of 12");
  });

  it("names a trade style only from a real, sufficiently sampled signal", () => {
    expect(tradeStyleFromSignals(null)).toBeNull();
    expect(tradeStyleFromSignals({ posture: { status: "insufficient_data", label: null } })).toBeNull();
    expect(
      tradeStyleFromSignals({
        posture: { status: "ok", label: "contending", summary: "Win-now." },
        pick_behavior: { status: "ok", label: "buys_picks", summary: "Hoards picks." },
      }),
    ).toEqual({ tag: "CONTENDER", blurb: "Win-now." });
  });
});
