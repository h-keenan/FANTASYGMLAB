import { describe, expect, it } from "vitest";

import { areaPath, bandPathFor, chartPlaceholder, chartSummary, fixedDomain, gapCaption, linePath, makeScales, niceDomain, prepareSeries, singleBarFraction, thinTicks, weeklyGapRows } from "./chartSeries";

const row = (x: number, y: number | null, gap?: "bye" | "injured" | "missing") => ({ x, y, gap });

describe("prepareSeries statuses", () => {
  it("is empty with no rows, or only gaps", () => {
    expect(prepareSeries([]).status).toBe("empty");
    expect(prepareSeries([row(1, null), row(2, null)]).status).toBe("empty");
  });
  it("one played point is a single (a stat, never a lone dot), even with gaps around it", () => {
    const s = prepareSeries([row(1, 25.7)]);
    expect(s.status).toBe("single");
    expect(chartPlaceholder(s.status)).toBe("Not enough weeks yet for a trend");
    expect(prepareSeries([row(1, null), row(2, 9), row(3, null)]).status).toBe("single");
  });
  it("a projection keeps one played week on a real chart", () => {
    const s = prepareSeries([row(1, 25.7)], { band: [{ x: 2, mean: 20, floor: 12, ceiling: 30 }, { x: 3, mean: 20, floor: 12, ceiling: 30 }] });
    expect(s.status).toBe("ready");
    expect(s.band).toHaveLength(2);
    expect(s.yDomain[1]).toBeGreaterThanOrEqual(30);
  });
  it("a projection alone (no played weeks) still draws", () => {
    expect(prepareSeries([], { band: [{ x: 1, mean: 5, floor: 1, ceiling: 9 }, { x: 2, mean: 6, floor: 2, ceiling: 10 }] }).status).toBe("ready");
  });
  it("two or three points are sparse, four or more are ready", () => {
    expect(prepareSeries([row(1, 5), row(2, 7)]).status).toBe("sparse");
    expect(prepareSeries([row(1, 5), row(2, 7), row(3, 6)]).status).toBe("sparse");
    expect(prepareSeries([row(1, 5), row(2, 7), row(3, 6), row(4, 9)]).status).toBe("ready");
  });
});

describe("gaps: bye, injured and missed weeks", () => {
  const s = prepareSeries([row(1, 10), row(2, 14), row(3, null, "bye"), row(4, null, "injured"), row(5, 20), row(6, 18)]);
  it("breaks the line into solid runs", () => {
    expect(s.segments.map((seg) => seg.map((p) => p.x))).toEqual([[1, 2], [5, 6]]);
  });
  it("bridges the gap with one dashed span from the last played to the next played point", () => {
    expect(s.bridges).toHaveLength(1);
    expect(s.bridges[0].from.x).toBe(2);
    expect(s.bridges[0].to.x).toBe(5);
  });
  it("puts a muted marker on every gap, interpolated on the bridge", () => {
    expect(s.gaps.map((g) => [g.x, g.kind, g.between])).toEqual([[3, "bye", true], [4, "injured", true]]);
    expect(s.gaps[0].y).toBeCloseTo(14 + (20 - 14) / 3, 5);
    expect(s.gaps[1].y).toBeCloseTo(14 + ((20 - 14) * 2) / 3, 5);
  });
  it("keeps the x domain across the gap, so no week disappears", () => {
    expect(s.xDomain).toEqual([1, 6]);
    expect(s.xTicks).toEqual([1, 2, 3, 4, 5, 6]);
  });
  it("leading and trailing gaps get a marker level with the nearest played point and no bridge", () => {
    const t = prepareSeries([row(1, null, "injured"), row(2, 8), row(3, 9), row(4, 7), row(5, null, "bye")]);
    expect(t.bridges).toHaveLength(0);
    expect(t.gaps.map((g) => [g.x, g.y, g.between])).toEqual([[1, 8, false], [5, 7, false]]);
    expect(t.segments).toHaveLength(1);
  });
  it("a one-week island between two gaps is its own run (a dot, bridged both sides)", () => {
    const t = prepareSeries([row(1, 4), row(2, null), row(3, 6), row(4, null), row(5, 8)]);
    expect(t.segments.map((seg) => seg.length)).toEqual([1, 1, 1]);
    expect(t.bridges).toHaveLength(2);
  });
  it("describes the gap kinds", () => {
    expect(gapCaption(s)).toBe("Dashed: bye, injured or missed weeks");
    expect(gapCaption(prepareSeries([row(1, 1), row(2, null, "bye"), row(3, 2)]))).toBe("Dashed: bye week");
    expect(gapCaption(prepareSeries([row(1, 1), row(2, 2)]))).toBeNull();
  });
  it("sorts unordered input and ignores bad x", () => {
    const t = prepareSeries([row(3, 3), row(1, 1), row(Number.NaN, 9), row(2, 2)]);
    expect(t.played.map((p) => p.x)).toEqual([1, 2, 3]);
  });
});

describe("axes", () => {
  it("includeZero pins the floor to 0 and rounds the top to a nice tick", () => {
    const s = prepareSeries([row(1, 12), row(2, 21), row(3, 25.7), row(4, 14)], { includeZero: true });
    expect(s.yDomain[0]).toBe(0);
    expect(s.yDomain[1]).toBeGreaterThanOrEqual(25.7);
    expect(s.yTicks[0]).toBe(0);
    expect(s.yTicks[s.yTicks.length - 1]).toBe(s.yDomain[1]);
  });
  it("clamps a rating to 0-99", () => {
    const s = prepareSeries([row(1, 97), row(2, 98), row(3, 99), row(4, 98)], { yPad: 3, clamp: [0, 99] });
    expect(s.yDomain[1]).toBeLessThanOrEqual(99);
  });
  it("a flat series still has a real span", () => {
    const s = prepareSeries([row(1, 5), row(2, 5), row(3, 5), row(4, 5)]);
    expect(s.yDomain[1]).toBeGreaterThan(s.yDomain[0]);
  });
  it("fixed domain for a rank chart keeps both ends", () => {
    const s = prepareSeries([row(0, 3), row(1, 1), row(2, 7)], { yDomain: [1, 12] });
    expect(s.yDomain).toEqual([1, 12]);
    expect(s.yTicks[0]).toBe(1);
    expect(s.yTicks[s.yTicks.length - 1]).toBe(12);
    expect(fixedDomain([1, 12], 4).ticks).toEqual([1, 5, 12]);
  });
  it("niceDomain and thinTicks", () => {
    expect(niceDomain(0, 26, 4).domain).toEqual([0, 30]);
    expect(thinTicks([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14], 6)).toEqual([1, 4, 7, 10, 13]);
    expect(thinTicks([1, 2, 3], 6)).toEqual([1, 2, 3]);
  });
});

describe("stats and copy", () => {
  it("peak, low, average and last ignore gaps", () => {
    const s = prepareSeries([row(1, 10), row(2, null), row(3, 20), row(4, 15), row(5, 5)]);
    expect(s.stats).toMatchObject({ count: 4, min: 5, max: 20, average: 12.5, last: 5 });
    expect(s.stats.peak?.x).toBe(3);
  });
  it("summary says what the chart says, including gaps", () => {
    const s = prepareSeries([row(1, 10), row(2, null), row(3, 20), row(4, 15)]);
    expect(chartSummary(s, "Micah Jennings", "pts")).toContain("3 weeks, average 15.0 pts, high 20.0, low 10.0, latest 15.0. 1 week with no data.");
    expect(chartSummary(prepareSeries([row(1, 25.7)]), "Micah Jennings", "pts")).toBe("Micah Jennings: one week so far, 25.7 pts.");
    expect(chartSummary(prepareSeries([]), "X", "pts")).toBe("X: no data yet.");
  });
  it("single mini bar fraction is bounded", () => {
    expect(singleBarFraction(25.7, [0, 30])).toBeCloseTo(0.857, 2);
    expect(singleBarFraction(99, [0, 30])).toBe(1);
    expect(singleBarFraction(-5, [0, 30])).toBe(0);
  });
});

describe("geometry", () => {
  const s = prepareSeries([row(1, 0), row(2, 10), row(3, 5), row(4, 10)], { includeZero: true });
  const scales = makeScales(s, 300, 100, { top: 10, right: 10, bottom: 10, left: 30 });
  it("maps the domain into the plot rect, y up", () => {
    expect(scales.x(1)).toBe(30);
    expect(scales.x(4)).toBe(290);
    expect(scales.y(s.yDomain[0])).toBe(90);
    expect(scales.y(s.yDomain[1])).toBe(10);
  });
  it("invert puts the low value on top", () => {
    const inv = makeScales(s, 300, 100, { top: 10, right: 10, bottom: 10, left: 30 }, true);
    expect(inv.y(s.yDomain[0])).toBe(10);
  });
  it("smooth line is monotone: never leaves the data's y range", () => {
    const pts = s.played.map((p) => ({ x: scales.x(p.x), y: scales.y(p.y) }));
    const nums = linePath(pts, true).match(/-?\d+(\.\d+)?/g)!.map(Number);
    const ys = nums.filter((_, i) => i % 2 === 1);
    expect(Math.min(...ys)).toBeGreaterThanOrEqual(Math.min(...pts.map((p) => p.y)) - 0.01);
    expect(Math.max(...ys)).toBeLessThanOrEqual(Math.max(...pts.map((p) => p.y)) + 0.01);
  });
  it("straight and area paths", () => {
    expect(linePath([{ x: 0, y: 0 }, { x: 10, y: 5 }], true)).toBe("M 0 0 L 10 5");
    expect(linePath([], true)).toBe("");
    expect(areaPath([{ x: 0, y: 0 }, { x: 10, y: 5 }], 20, false)).toBe("M 0 0 L 10 5 L 10 20 L 0 20 Z");
    expect(areaPath([{ x: 0, y: 0 }], 20)).toBe("");
  });
  it("band polygon", () => {
    const b = prepareSeries([], { band: [{ x: 1, mean: 5, floor: 2, ceiling: 8 }, { x: 2, mean: 5, floor: 2, ceiling: 8 }] });
    const sc = makeScales(b, 100, 100, { top: 0, right: 0, bottom: 0, left: 0 });
    expect(bandPathFor(b.band, sc).startsWith("M ")).toBe(true);
    expect(bandPathFor(b.band.slice(0, 1), sc)).toBe("");
  });
});

describe("weeklyGapRows", () => {
  it("fills missed weeks inside the range, marks listed byes, never extends past the last reported week", () => {
    const rows = weeklyGapRows([{ week: 1, points: 25.7 }, { week: 4, points: 10 }, { week: 3, points: null }], [2]);
    expect(rows.map((r) => [r.x, r.y, r.gap])).toEqual([[1, 25.7, "missing"], [2, null, "bye"], [3, null, "missing"], [4, 10, "missing"]]);
    expect(rows[1].label).toBe("Wk 2");
  });
  it("no rows for no weeks", () => {
    expect(weeklyGapRows([])).toEqual([]);
  });
  it("feeds prepareSeries: a bye in the middle is a bridged gap, one week alone is single", () => {
    const s = prepareSeries(weeklyGapRows([{ week: 1, points: 10 }, { week: 3, points: 14 }, { week: 4, points: 12 }, { week: 5, points: 15 }], [2]));
    expect(s.gaps.map((g) => [g.x, g.kind])).toEqual([[2, "bye"]]);
    expect(prepareSeries(weeklyGapRows([{ week: 1, points: 25.7 }])).status).toBe("single");
  });
});
