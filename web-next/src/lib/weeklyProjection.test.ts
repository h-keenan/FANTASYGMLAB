import { describe, expect, it } from "vitest";

import { buildWeeklyChartRows, isFlatProjection } from "./weeklyProjection";

describe("weekly chart rows", () => {
  it("spans played weeks and the weeks ahead, with gaps as nulls", () => {
    const rows = buildWeeklyChartRows(
      [{ week: 1, points: 10 }, { week: 2, points: 4 }],
      [{ week: 4, mean: 7, floor: 3, ceiling: 11 }, { week: 5, mean: 7, floor: 3, ceiling: 11 }],
    );
    expect(rows.map((r) => r.week)).toEqual([1, 2, 3, 4, 5]);
    expect(rows[2]).toMatchObject({ actual: null, mean: null });
    expect(rows[0]).toMatchObject({ actual: 10, mean: null });
    expect(rows[3]).toMatchObject({ actual: null, mean: 7, floor: 3, ceiling: 11 });
  });
  it("is empty with nothing to plot", () => {
    expect(buildWeeklyChartRows([], null)).toEqual([]);
  });
  it("detects a flat projection", () => {
    expect(isFlatProjection([{ mean: 2.2, floor: 0.6, ceiling: 3.8 }, { mean: 2.2, floor: 0.6, ceiling: 3.8 }])).toBe(true);
    expect(isFlatProjection([{ mean: 2.2, floor: 0.6, ceiling: 3.8 }, { mean: 2.4, floor: 0.6, ceiling: 3.8 }])).toBe(false);
  });
});
