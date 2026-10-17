import { describe, expect, it } from "vitest";

import { fillWeeklyPointGaps } from "./playerComparePresentation";
import type { WeeklyStatPoint } from "./api";

function point(week: number, points: number | null): WeeklyStatPoint {
  return { week, fantasy_points_ppr: points, snap_share: null };
}

describe("fillWeeklyPointGaps", () => {
  it("inserts a null-points entry for a bye week sandwiched between played weeks", () => {
    const dense = fillWeeklyPointGaps([point(1, 18.4), point(2, 9.1), point(4, 22.0)]);

    expect(dense.map((week) => week.week)).toEqual([1, 2, 3, 4]);
    expect(dense[2]).toEqual({ week: 3, fantasy_points_ppr: null, snap_share: null });
  });

  it("never extrapolates past the latest reported week", () => {
    const dense = fillWeeklyPointGaps([point(1, 10), point(2, 12)]);

    expect(dense.map((week) => week.week)).toEqual([1, 2]);
  });

  it("is a no-op when the series is already dense", () => {
    const input = [point(1, 10), point(2, 12), point(3, 14)];

    expect(fillWeeklyPointGaps(input)).toEqual(input);
  });

  it("leaves an empty series alone", () => {
    expect(fillWeeklyPointGaps([])).toEqual([]);
  });

  it("handles out-of-order input the same as sorted input", () => {
    const dense = fillWeeklyPointGaps([point(4, 22.0), point(1, 18.4), point(2, 9.1)]);

    expect(dense.map((week) => week.week)).toEqual([1, 2, 3, 4]);
  });
});
