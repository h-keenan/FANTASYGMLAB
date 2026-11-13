import { describe, expect, it } from "vitest";

import { rowsAsOf, simAsOfSeason, simDefaultStartYear } from "./simAsOf";

describe("sim as-of cut", () => {
  it("the sim replays the season in progress or next up; real data stops at the season before", () => {
    expect(simDefaultStartYear(new Date(2026, 10, 13))).toBe(2026); // Nov 2026
    expect(simDefaultStartYear(new Date(2027, 0, 20))).toBe(2026); // Jan-Feb still belongs to the season just played
    expect(simDefaultStartYear(new Date(2027, 2, 1))).toBe(2027);
    expect(simAsOfSeason(2026)).toBe(2025);
    expect(simAsOfSeason(2028)).toBe(2027);
    expect(simAsOfSeason(0, new Date(2026, 10, 13))).toBe(2025);
    expect(simAsOfSeason(undefined, new Date(2026, 10, 13))).toBe(2025);
  });
  it("keeps seasons up to the cut, drops later and unplaceable rows", () => {
    const rows = [{ season: 2024, n: "a" }, { season: 2025, n: "b" }, { season: 2026, n: "c" }, { season: null, n: "d" }];
    expect(rowsAsOf(rows, 2025).map((r) => r.n)).toEqual(["a", "b"]);
    expect(rowsAsOf(rows, 2023)).toEqual([]);
  });
});
