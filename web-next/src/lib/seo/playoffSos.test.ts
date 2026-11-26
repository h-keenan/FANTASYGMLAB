import { describe, expect, it } from "vitest";

import { hasUsableSos, parsePlayoffSos, rankedAt, scheduleLine } from "./playoffSos";
import { MIN_ROOKIES, rookieRows } from "./rookies";

const team = (code: string, rank: number | null) => ({
  team: code,
  confidence: "high",
  opponents: [
    { week: 15, opponent: "DEN", is_home: true },
    { week: 16, opponent: "LV", is_home: false },
    { week: 17, opponent: null, is_home: null },
  ],
  by_position: rank === null ? {} : { QB: { avg_points_allowed: 18.2, vs_league_avg_pct: 3.1, rank_easiest: rank, of: 32 } },
});

const payload = (teams: unknown[], status = "ok") => ({ status, generated_at: "2026-11-26T00:00:00Z", season: 2026, weeks: [15, 16, 17], methodology: "m", teams });

describe("playoff SOS parsing", () => {
  it("rejects malformed payloads and treats an empty ok as unavailable", () => {
    expect(parsePlayoffSos(null)).toBeNull();
    expect(parsePlayoffSos({ season: 2026 })).toBeNull();
    expect(parsePlayoffSos(payload([]))?.status).toBe("unavailable");
  });

  it("ranks easiest first and skips teams without a rating", () => {
    const sos = parsePlayoffSos(payload([team("B", 2), team("A", 1), team("C", null)]))!;
    expect(rankedAt(sos, "QB").map((r) => r.team.team)).toEqual(["A", "B"]);
    expect(rankedAt(sos, "RB")).toEqual([]);
  });

  it("formats the schedule line with home/away and byes", () => {
    expect(scheduleLine(team("A", 1) as never)).toBe("W15 vs DEN, W16 @ LV, W17 BYE");
  });

  it("needs a near-full league of teams to be usable", () => {
    expect(hasUsableSos(parsePlayoffSos(payload([team("A", 1)])))).toBe(false);
    expect(hasUsableSos(parsePlayoffSos(payload(Array.from({ length: 20 }, (_, i) => team(`T${i}`, i + 1)))))).toBe(true);
    expect(hasUsableSos(null)).toBe(false);
  });
});

describe("rookieRows", () => {
  const mk = (id: string, rank: number, yrs: number | null) => ({
    player_id: id, name: id, position: "WR", team: null, age: 21, years_exp: yrs, status: null, injury_status: null,
    score: 1000, overall_rank: rank, position_rank: rank, tier: null, overall_rating: null, trend: null,
  });
  const board = (players: ReturnType<typeof mk>[]) => ({ format: "1qb" as const, tep: false, scoring: "PPR", teams: 12, generated_at: "", source_updated_at: "", players });

  it("keeps only first-year players, best first, and pairs the Superflex row", () => {
    const rows = rookieRows(board([mk("vet", 1, 4), mk("r2", 30, 0), mk("r1", 20, 0), mk("unk", 5, null)]), board([mk("r1", 18, 0)]));
    expect(rows.map((r) => r.player.player_id)).toEqual(["r1", "r2"]);
    expect(rows[0].superflex?.overall_rank).toBe(18);
    expect(rows[1].superflex).toBeNull();
    expect(MIN_ROOKIES).toBeGreaterThan(2);
  });
});
