import { describe, expect, it } from "vitest";

import type { PlayoffOddsTeam, TeamRanking } from "@/lib/api";
import { buildPlanSnapshot, deadlineBanner } from "@/lib/gmPlanSnapshot";

const ranking = {
  power_rank: 3,
  draft_capital_rank: 7,
  starter_rank: 3,
  bench_rank: 12,
  age_rank: 2,
  wins: 2,
  losses: 4,
  ties: 0,
} as unknown as TeamRanking;
const odds = { playoff_probability: 55.4, median_seed: 6 } as PlayoffOddsTeam;

describe("buildPlanSnapshot", () => {
  it("builds every tile from real rows", () => {
    const tiles = buildPlanSnapshot(ranking, 12, odds);
    expect(tiles.map((t) => t.key)).toEqual(["power", "capital", "odds", "record", "starter", "bench", "age"]);
    expect(tiles[0]).toMatchObject({ value: "3 of 12", fill: 10 / 12 });
    expect(tiles[2]).toMatchObject({ value: "55%", note: "Proj. 6-seed" });
    expect(tiles[3].value).toBe("2 - 4");
    expect(tiles[5].fill).toBeCloseTo(1 / 12);
  });

  it("omits the seed note and missing tiles instead of inventing them", () => {
    const tiles = buildPlanSnapshot(ranking, 12, { ...odds, median_seed: 0 });
    expect(tiles.find((t) => t.key === "odds")?.note).toBeUndefined();
    expect(buildPlanSnapshot(null, 12, null)).toEqual([]);
    expect(buildPlanSnapshot({ ...ranking, draft_capital_rank: null } as TeamRanking, 12, null).some((t) => t.key === "capital")).toBe(false);
  });
});

describe("deadlineBanner", () => {
  it("shows only before the real deadline", () => {
    expect(deadlineBanner({ trade_deadline_week: 11, current_week: 6, trade_deadline_passed: false, message: "" })).toEqual({ kind: "upcoming", week: 11 });
    expect(deadlineBanner({ trade_deadline_week: 11, current_week: 12, trade_deadline_passed: true, message: "" })).toBeNull();
    expect(deadlineBanner({ trade_deadline_week: null, current_week: 6, trade_deadline_passed: false, message: "" })).toBeNull();
    expect(deadlineBanner(undefined)).toBeNull();
  });
});
