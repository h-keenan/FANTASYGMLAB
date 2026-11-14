import { describe, expect, it } from "vitest";

import type { SimPlayerWeek } from "./simGame";
import { simActualPoints, simAvailabilityLine, simHeroGrade, simProjectionBand, simProjectionIsFlat, simRosLine } from "./simPlayerSheet";

const wk = (week: number, projection: number, extra: Partial<SimPlayerWeek> = {}): SimPlayerWeek => ({ week, projection, floor: projection * 0.3, ceiling: projection * 1.7, bye: false, out: false, ...extra });

describe("flat projection suppression", () => {
  const flatWeeks = [3, 4, 5, 6].map((w) => wk(w, 2.2));
  it("treats identical playable weeks as flat and draws no band", () => {
    expect(simProjectionIsFlat({ weeks: flatWeeks })).toBe(true);
    expect(simProjectionBand({ weeks: flatWeeks })).toBeNull();
  });
  it("a bye or out week alone is not variation", () => {
    const weeks = [wk(3, 2.2), wk(4, 0, { bye: true }), wk(5, 0, { out: true }), wk(6, 2.2)];
    expect(simProjectionIsFlat({ weeks })).toBe(true);
  });
  it("charts the band when weeks genuinely differ, leaving bye and out weeks as gaps", () => {
    const weeks = [wk(3, 8), wk(4, 9.5), wk(5, 0, { bye: true }), wk(6, 7)];
    expect(simProjectionIsFlat({ weeks })).toBe(false);
    expect(simProjectionBand({ weeks })?.map((p) => p.week)).toEqual([3, 4, 6]);
  });
  it("trusts the server flag over the weeks", () => {
    expect(simProjectionIsFlat({ weeks: [wk(3, 8), wk(4, 9)], projection_flat: true })).toBe(true);
  });
  it("prints one rest-of-season line", () => {
    expect(simRosLine({ mean: 2.2, floor: 0.6, ceiling: 3.8 })).toBe("Rest of season: 2.2 ppg (0.6-3.8)");
    expect(simAvailabilityLine({ bye_week: 7, out_weeks: [3, 4] })).toBe("Bye week 7 · Out weeks 3-4");
    expect(simAvailabilityLine({ bye_week: null, out_weeks: [] })).toBeNull();
  });
  it("maps history to actual points", () => {
    expect(simActualPoints({ history: [{ week: 1, points: 11.2 }] })).toEqual([{ week: 1, points: 11.2 }]);
    expect(simActualPoints({})).toEqual([]);
  });
});

describe("hero grade (the PQV adapter)", () => {
  it("hands the hero a letter grade and nothing numeric", () => {
    expect(simHeroGrade({ grade: "A-", grade_range: ["B+", "A"], grade_uncertain: true })).toEqual({ grade: "A-", grade_range: ["B+", "A"], grade_uncertain: true });
    expect(simHeroGrade({ grade: null })).toBeNull();
  });
});
