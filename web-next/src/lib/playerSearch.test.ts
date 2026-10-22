import { describe, expect, it } from "vitest";

import { matchPlayersByName } from "./playerSearch";

const pool = [
  { name: "Ja'Marr Chase" },
  { name: "Travis Kelce" },
  { name: "Kenneth Walker III" },
  { name: "Mike Evans" },
  { name: null },
  { name: "Ken Mackel" },
];

const names = (rows: Array<{ name: string | null }>) => rows.map((p) => p.name);

describe("matchPlayersByName", () => {
  it("needs at least two characters", () => {
    expect(matchPlayersByName(pool, "")).toEqual([]);
    expect(matchPlayersByName(pool, " k ")).toEqual([]);
  });

  it("ranks name prefix, then word prefix, then mid-word, keeping pool order", () => {
    expect(names(matchPlayersByName(pool, "ke"))).toEqual(["Kenneth Walker III", "Ken Mackel", "Travis Kelce", "Mike Evans"]);
    expect(names(matchPlayersByName(pool, "kel"))).toEqual(["Travis Kelce", "Ken Mackel"]);
  });

  it("is case-insensitive, trims, skips nameless rows, and honours the limit", () => {
    expect(names(matchPlayersByName(pool, "  CHASE "))).toEqual(["Ja'Marr Chase"]);
    expect(matchPlayersByName(pool, "ke", 1)).toHaveLength(1);
  });
});
