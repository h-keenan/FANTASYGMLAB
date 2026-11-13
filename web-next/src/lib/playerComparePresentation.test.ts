import { describe, expect, it, vi } from "vitest";

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

import {
  buildHeadlineRows,
  buildHeadlineTextRows,
  compareRowWinner,
  nextProjection,
  ppgFromWeeks,
  readRecentOpponents,
  rememberOpponent,
  scheduleOutlook,
  suggestedOpponents,
} from "./playerComparePresentation";
import type { RankedPlayer, ScheduleWeek } from "./api";

function rp(id: string, position: string, score: number, over: Partial<RankedPlayer> = {}): RankedPlayer {
  return { player_id: id, name: id, position, team: "KC", age: 25, status: null, injury_status: null, tier: null, score, overall_rank: 1, position_rank: 1, rank_unavailable_reason: null, opportunity_label: null, ...over };
}
function game(over: Partial<ScheduleWeek>): ScheduleWeek {
  return { week: 10, opponent: "DAL", is_home: true, spread_line: null, total_line: null, played: false, team_score: null, opponent_score: null, bye: false, opponent_defense_tier: null, projection: null, ...over };
}

describe("compare page v2 helpers", () => {
  it("PPG averages the played weeks and is null before any game", () => {
    expect(ppgFromWeeks([point(1, 10), point(2, 20), point(3, null)])).toBe(15);
    expect(ppgFromWeeks([point(1, null)])).toBeNull();
  });
  it("next projection skips played games, byes and non-ok projections", () => {
    const ok = { status: "ok" as const, point_estimate: 13.5, low: 1, high: 2, confidence: "high" as const, opponent: "DAL" };
    expect(nextProjection([game({ played: true, projection: ok }), game({ bye: true }), game({ projection: { ...ok, status: "no_schedule_data" } }), game({ projection: ok })])).toBe(13.5);
    expect(nextProjection([])).toBeNull();
  });
  it("schedule outlook counts the next four games by tier; soft minus tough decides the winner", () => {
    const soft = scheduleOutlook([game({ opponent_defense_tier: "weak" }), game({ opponent_defense_tier: "weak" }), game({ opponent_defense_tier: "tough" }), game({ opponent_defense_tier: "average" }), game({ opponent_defense_tier: "tough" })]);
    expect(soft).toEqual({ score: 1, text: "2 soft · 1 avg · 1 tough" });
    expect(scheduleOutlook([game({})])).toBeNull();
    const a = { ppg: null, projection: null, schedule: soft };
    const b = { ppg: null, projection: null, schedule: { score: -1, text: "1 tough" } };
    expect(buildHeadlineTextRows(null, null, a, b).find((r) => r.label === "Next 4 games")?.winner).toBe("a");
  });
  it("headline rows mark the better side but never pick a winner on age", () => {
    const rows = buildHeadlineRows(rp("a", "WR", 100, { age: 22 }), rp("b", "WR", 90, { age: 30 }), { ppg: 12, projection: 10, schedule: null }, { ppg: 14, projection: null, schedule: null });
    const byLabel = Object.fromEntries(rows.map((r) => [r.label, compareRowWinner(r)]));
    expect(byLabel["Value Score"]).toBe("a");
    expect(byLabel["PPG"]).toBe("b");
    expect(byLabel["Age"]).toBeNull();
    expect(byLabel["Next game"]).toBeNull();
  });
  it("suggests the same position at the nearest value, excluding the base and anyone excluded", () => {
    const base = rp("base", "WR", 1000);
    const pool = [base, rp("far", "WR", 100), rp("near", "WR", 990), rp("nearer", "WR", 1005), rp("rb", "RB", 1000), rp("skip", "WR", 999)];
    expect(suggestedOpponents(pool, base, ["skip"], 2).map((p) => p.player_id)).toEqual(["nearer", "near"]);
  });
  it("remembers recent opponents newest first, deduped and capped, and survives blocked storage", () => {
    window.localStorage.clear();
    for (const id of ["1", "2", "3", "4", "5", "6", "7", "2"]) rememberOpponent("L", id);
    expect(readRecentOpponents("L")).toEqual(["2", "7", "6", "5", "4", "3"]);
    const spy = vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    expect(readRecentOpponents("L")).toEqual([]);
    spy.mockRestore();
  });
});
