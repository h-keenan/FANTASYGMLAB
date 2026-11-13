import { describe, expect, it } from "vitest";

import { simCollegeTiles, simCurveBand, simCurveCaption, simDraftLine, simFmtScoutStat, simOrdinal, simTagConfidenceLabel } from "./simScouting";
import type { SimScoutingCollege } from "./simGame";

const college: SimScoutingCollege = {
  columns: [{ key: "rush_yd", label: "Rush yds", fmt: "int" }, { key: "ypc", label: "Yds/carry", fmt: "num1" }, { key: "missing", label: "X", fmt: "int" }],
  seasons: [{ season: 2026, team: "Summit Tech", class: "SR", games: 13, stats: { rush_yd: 1413, ypc: 5.6 } }],
  career: {}, percentiles: { rush_yd: 75 }, final: { season: 2026, team: "Summit Tech", games: 13, stats: { rush_yd: 1413, ypc: 5.6 } },
};

describe("scouting presentation", () => {
  it("builds stat tiles from the payload's own columns (so real stats slot in unchanged)", () => {
    expect(simCollegeTiles(college)).toEqual([
      { label: "Rush yds", value: "1,413", note: "", percentile: 75 },
      { label: "Yds/carry", value: "5.6", note: "", percentile: null },
    ]);
    expect(simFmtScoutStat(24.1, "pct1")).toBe("24.1%");
    expect(simFmtScoutStat(2.5, "num2")).toBe("2.50");
  });
  it("turns the development curve into a chart band and a caption", () => {
    const dev = { points: [{ year: 1, mean: 9, lo: 9, hi: 9 }, { year: 5, mean: 7.4, lo: 5.6, hi: 9.8 }] };
    expect(simCurveBand(dev)[1]).toEqual({ week: 5, mean: 7.4, floor: 5.6, ceiling: 9.8 });
    expect(simCurveCaption(dev)).toBe("Year 1 9.0 → Year 5 7.4 ppg");
    expect(simCurveCaption({ points: [] })).toBe("");
  });
  it("labels draft slot, ordinals and tag confidence", () => {
    expect(simDraftLine({ round: 2, pick: 41, class_rank: 17, class_size: 60, basis: "" })).toBe("Round 2 · Pick 41");
    expect([1, 2, 3, 11, 12, 22, 93].map(simOrdinal)).toEqual(["1st", "2nd", "3rd", "11th", "12th", "22nd", "93rd"]);
    expect([0.2, 0.5, 0.9].map(simTagConfidenceLabel)).toEqual(["Low", "Medium", "High"]);
  });
});
