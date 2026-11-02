import { describe, expect, it } from "vitest";

import { formatPoints, leanLabel, rangeDisplayRows } from "./startSitRange";

describe("startSitRange helpers", () => {
  it("labels the lean", () => {
    expect(leanLabel("ceiling")).toBe("Ceiling play");
    expect(leanLabel("floor")).toBe("Floor play");
  });

  it("formats points to one decimal", () => {
    expect(formatPoints(12)).toBe("12.0");
    expect(formatPoints(7.25)).toBe("7.3");
  });

  it("drops sides with no real range and marks the favored one", () => {
    const a = { name: "A", projected: 10, low: 5, high: 15 };
    const rows = rangeDisplayRows(
      [
        { key: "start", label: "Start", range: a },
        { key: "over", label: "Over", range: null },
      ],
      "start",
    );
    expect(rows).toHaveLength(1);
    expect(rows[0]).toMatchObject({ key: "start", name: "A", favored: true });
    expect(rangeDisplayRows([{ key: "start", label: "Start", range: a }], null)[0].favored).toBe(false);
  });
});
