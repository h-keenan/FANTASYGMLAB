import { describe, expect, it } from "vitest";

import { cardRows, seeAllLabel, signalPills, signalSpokenLabel, strategyTone, visibleSignalRows, type DraftSignalRow } from "./draftSignals";

const row = (over: Partial<DraftSignalRow> = {}): DraftSignalRow => ({
  team_id: "2",
  team_name: "Retooler",
  avatar_url: null,
  strategy: "retool",
  strategy_display: "Retool",
  draft_rank: 10,
  draft_rank_tied: false,
  future_rank: 10,
  future_rank_tied: false,
  firsts: 0,
  reason_code: "too_few_picks",
  reason_short: "Too few picks for a retool",
  reason_long: "Draft rank #10 leaves too little flexibility for a retool build.",
  evidence: [],
  ...over,
});

describe("draftSignals", () => {
  it("collapses equal draft and future ranks into one Picks pill (no doubled number)", () => {
    expect(signalPills(row())).toEqual([{ key: "picks", label: "Picks #10" }]);
  });
  it("keeps two pills when the ranks differ, and marks ties", () => {
    expect(signalPills(row({ future_rank: 7, draft_rank_tied: true }))).toEqual([
      { key: "draft", label: "Draft T-#10" },
      { key: "future", label: "Future #7" },
    ]);
  });
  it("skips missing ranks", () => {
    expect(signalPills(row({ draft_rank: null, future_rank: 4 }))).toEqual([{ key: "future", label: "Future #4" }]);
    expect(signalPills(row({ draft_rank: null, future_rank: null }))).toEqual([]);
  });
  it("maps direction to a tone", () => {
    expect(strategyTone("contender")).toBe("success");
    expect(strategyTone("retool")).toBe("warning");
    expect(strategyTone("rebuild")).toBe("accent");
    expect(strategyTone("")).toBe("neutral");
  });
  it("shows the top 3 and offers See all (n) only when there is more", () => {
    const rows = [1, 2, 3, 4, 5];
    expect(visibleSignalRows(rows, false)).toEqual([1, 2, 3]);
    expect(visibleSignalRows(rows, true)).toEqual(rows);
    expect(seeAllLabel(5)).toBe("See all (5)");
    expect(seeAllLabel(3)).toBeNull();
  });
  it("speaks one line and falls back to legacy strings when rows are absent", () => {
    expect(signalSpokenLabel(row())).toBe("Retooler, Picks #10, Retool, Too few picks for a retool");
    expect(cardRows({ rows: [] })).toBeNull();
    expect(cardRows({})).toBeNull();
    expect(cardRows({ rows: [row()] })).toHaveLength(1);
  });
});
