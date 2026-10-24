import { describe, expect, it } from "vitest";

import type { BriefingItem, ThisWeek, ThisWeekRow } from "@/lib/api";
import { buildTodayPlan, todayTitle } from "./todayPlan";

const row = (key: ThisWeekRow["key"], over: Partial<ThisWeekRow> = {}): ThisWeekRow => ({
  key, status: "S", tone: "neutral", headline: key, why: "w", cta_label: "go", route: "matchup", player_id: "", ...over,
});
const wk = (rows: ThisWeekRow[]): ThisWeek => ({ mode: "in_season", week: 3, rows, next_action: null });
const card = (over: Partial<BriefingItem> = {}) =>
  ({ category: "top_priority", headline: "H", destination: "my_team", route_player_id: "", ...over }) as BriefingItem;
const SUN = new Date(2026, 9, 25, 12);
const WED = new Date(2026, 9, 21, 12);
const keys = (p: ReturnType<typeof buildTodayPlan>) => p.today.map((e) => (e.kind === "row" ? e.row.key : "card"));

describe("buildTodayPlan", () => {
  it("game day: lineup today, waiver and trade later", () => {
    const p = buildTodayPlan(wk([row("lineup"), row("waiver"), row("trade")]), [], SUN);
    expect(keys(p)).toEqual(["lineup"]);
    expect(p.later.map((r) => r.key)).toEqual(["waiver", "trade"]);
  });

  it("waiver day: waiver today, healthy lineup later, risk lineup still first", () => {
    expect(keys(buildTodayPlan(wk([row("lineup"), row("waiver")]), [], WED))).toEqual(["waiver"]);
    const r = buildTodayPlan(wk([row("lineup", { tone: "risk" }), row("waiver")]), [card()], WED);
    expect(keys(r)).toEqual(["lineup", "card", "waiver"]);
  });

  it("dedupes trade card vs row and waiver row vs waiver card; ignores non top-priority", () => {
    const trade = row("trade", { status: "Idea", headline: "Idea X" });
    const p = buildTodayPlan(
      wk([trade, row("waiver", { player_id: "9" })]),
      [card({ headline: "Idea X" }), card({ headline: "Add", destination: "waivers", route_player_id: "9" }), card({ category: "watch", headline: "W" })],
      WED,
    );
    expect(p.dropped.items).toHaveLength(1);
    expect(p.dropped.rows.map((r) => r.key)).toEqual(["waiver"]);
    expect(p.today.filter((e) => e.kind === "card")).toHaveLength(1);
  });

  it("empty and title", () => {
    expect(buildTodayPlan(null, [], SUN).isEmpty).toBe(true);
    expect(todayTitle(wk([]))).toBe("Today · Week 3");
    expect(todayTitle(null)).toBe("Today");
  });
});
