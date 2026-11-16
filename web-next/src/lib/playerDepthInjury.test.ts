import { describe, expect, it } from "vitest";

import { depthChange, depthChartParts, depthRowKind, injuryHistoryRows, injurySummaryParts, weeksLabel, type DepthChartData, type InjuryRecordData } from "./playerDepthInjury";
import { compactSummaryText } from "./compactModule";

const chart: DepthChartData = {
  ok: true, team: "KC", slot: "RB", slot_label: "Running backs", self_order: 2, total: 3,
  entries: [
    { player_id: "a", name: "Starter", order: 1, is_self: false, change: 0 },
    { player_id: "b", name: "Me", order: 2, is_self: true, change: -1 },
    { player_id: "c", name: "Third", order: 4, is_self: false, change: null },
  ],
};

const record: InjuryRecordData = {
  ok: true, current_season: 2026, since_season: 2021, career_games_missed: 5,
  current: { label: "Questionable", status: "Questionable", severity: "question", unavailable: false, body_part: "Hamstring", practice: "Limited in practice", report: null, line: "Hamstring · Questionable" },
  seasons: [
    { season: 2026, games_missed: 2, stints: [{ start_week: 1, end_week: 1, games_missed: 1, injury: "Ankle" }, { start_week: 9, end_week: 9, games_missed: 1, injury: null }] },
    { season: 2023, games_missed: 3, stints: [{ start_week: 4, end_week: 6, games_missed: 3, injury: "Foot" }] },
  ],
};

describe("playerDepthInjury", () => {
  it("summarises a depth slot with his role, team, who is ahead and his move", () => {
    expect(compactSummaryText(depthChartParts(chart))).toBe("RB2 · KC · 1 ahead · Down 1");
    expect(depthChartParts({ ...chart, self_order: null })).toEqual([]);
  });
  it("classifies rows and moves", () => {
    expect(chart.entries.map((e) => depthRowKind(e, 2))).toEqual(["ahead", "self", "behind"]);
    expect(depthChange(2)?.arrow).toBe("up");
    expect(depthChange(0)).toBeNull();
    expect(depthChange(null)).toBeNull();
  });
  it("leads the injury summary with the current line, this season and career games missed", () => {
    expect(compactSummaryText(injurySummaryParts(record))).toBe("Hamstring · Questionable · 2 games missed in 2026 · 5 career");
    expect(compactSummaryText(injurySummaryParts({ ...record, current: null, seasons: [], career_games_missed: 0 }))).toBe("Healthy · No games missed on record");
  });
  it("lists stints newest first with week ranges and an honest unspecified injury", () => {
    const rows = injuryHistoryRows(record);
    expect(rows.map((r) => [r.season, r.injury, r.weeks, r.games])).toEqual([
      [2026, "Injury (not specified)", "Wk 9", "1 game"],
      [2026, "Ankle", "Wk 1", "1 game"],
      [2023, "Foot", "Wk 4–6", "3 games"],
    ]);
    expect(weeksLabel({ start_week: null, end_week: null, games_missed: 1, injury: null })).toBe("");
  });
});
