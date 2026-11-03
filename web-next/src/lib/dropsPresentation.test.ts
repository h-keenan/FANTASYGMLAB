import { describe, expect, it } from "vitest";

import {
  limitedDataNote,
  lineupEffectText,
  needsHeadline,
  ordinal,
  teamNeedStat,
  valueEffectText,
} from "./dropsPresentation";

const effect = { lineup_points_ros: -3.4, lineup_points_per_week: -0.4, this_week: 0, value_delta: -412, score: -500, weeks: 9 };

describe("dropsPresentation", () => {
  it("formats ordinals", () => {
    expect([1, 2, 3, 4, 8, 11, 12, 13, 21, 22].map(ordinal)).toEqual(["1st", "2nd", "3rd", "4th", "8th", "11th", "12th", "13th", "21st", "22nd"]);
  });

  it("formats lineup and value effects, hiding noise", () => {
    expect(lineupEffectText(effect)).toBe("-3 lineup pts over 9 weeks");
    expect(lineupEffectText({ ...effect, lineup_points_ros: 0.2 })).toBe("No lineup change");
    expect(valueEffectText(effect)).toBe("Value -412");
    expect(valueEffectText({ ...effect, value_delta: 40 })).toBe("");
  });

  it("never answers 'None': Covered only from the model, an em dash when it failed", () => {
    expect(teamNeedStat({ needs_model: null, needed_positions: [] })).toBe("—");
    expect(teamNeedStat({ needs_model: null, needed_positions: ["RB", "QB"] })).toBe("RB/QB");
    expect(needsHeadline({ needs_model: null, needed_positions: [] })).toMatch(/could not be fully modeled/);
  });

  it("builds the limited-data note from model_status", () => {
    expect(limitedDataNote({ degraded: false, reasons: [] })).toBeNull();
    expect(limitedDataNote({ degraded: true, reasons: [{ code: "x", message: "Lookup failed." }] })).toBe("Limited data: Lookup failed.");
  });
});
