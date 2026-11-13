import { describe, expect, it } from "vitest";

import { SIM_ASSET_ALL, simAdvanceState, simAutoSetMessage, simLineupDiff, simFilterGroups, simGroupByPosition, simSideSummary, simTradeFit, SIM_REVIEW_VIEWS, simReviewViewFor, simOpenKey, simParseOpen, simPreview, simSeeAllLabel, simWindow } from "./simLayout";

describe("simLayout", () => {
  it("namespaces and parses open state", () => {
    expect(simOpenKey("home.injuries")).toBe("fgl:sim-open:home.injuries");
    expect(simParseOpen("1", false)).toBe(true);
    expect(simParseOpen("0", true)).toBe(false);
    expect(simParseOpen(null, true)).toBe(true);
    expect(simParseOpen("junk", false)).toBe(false);
  });
  it("previews the first rows and reports the rest", () => {
    expect(simPreview([1, 2, 3, 4, 5], false, 3)).toEqual({ shown: [1, 2, 3], hidden: 2 });
    expect(simPreview([1, 2, 3, 4, 5], true, 3)).toEqual({ shown: [1, 2, 3, 4, 5], hidden: 0 });
    expect(simPreview([1, 2], false, 3).hidden).toBe(0);
    expect(simSeeAllLabel(2, false, "players")).toBe("See all (2 players)");
    expect(simSeeAllLabel(2, true)).toBe("Show less");
  });
  it("windows long lists", () => {
    expect(simWindow(Array.from({ length: 50 }, (_, i) => i), 20)).toMatchObject({ remaining: 30 });
    expect(simWindow([1], 20)).toEqual({ shown: [1], remaining: 0 });
  });
  it("assigns every review section to a tab", () => {
    const ids = ["grade", "decisions", "moves", "swings", "injuries", "champion-path", "your-path", "journey", "stats", "leaders", "your-leaders", "closest-yours", "closest-league"];
    const tabs = new Set(SIM_REVIEW_VIEWS.map((v) => v.value));
    for (const id of ids) expect(tabs.has(simReviewViewFor(id))).toBe(true);
    expect(simReviewViewFor("grade")).toBe("overview");
    expect(simReviewViewFor("swings")).toBe("awards");
    expect(simReviewViewFor("leaders")).toBe("stats");
    expect(simReviewViewFor("something-new")).toBe("overview");
  });
  it("groups trade assets by position, filters by chip and search, and totals a side", () => {
    const roster = [
      { id: "1", name: "Quinn Back", pos: "QB", value: 80 },
      { id: "2", name: "Ray Runner", pos: "RB", value: 60.4 },
      { id: "3", name: "Rob Rush", pos: "RB", value: 40 },
      { id: "4", name: "Kyle Kick", pos: "K", value: 5 },
    ];
    const groups = simGroupByPosition(roster, ["QB", "RB", "WR", "TE", "K"]);
    expect(groups.map((g) => [g.key, g.items.length])).toEqual([["QB", 1], ["RB", 2], ["K", 1]]);
    expect(groups.every((g) => g.kind === "player")).toBe(true);
    expect(simFilterGroups(groups, "RB", "").map((g) => g.key)).toEqual(["RB"]);
    expect(simFilterGroups(groups, SIM_ASSET_ALL, "rush").map((g) => g.items[0].id)).toEqual(["3"]);
    expect(simSideSummary(roster.slice(0, 2))).toEqual({ count: 2, value: 140 });
    expect(simGroupByPosition([{ pos: "DEF", name: "x" }], ["QB"])[0].key).toBe("OTHER");
  });
  it("computes roster room after a trade", () => {
    expect(simTradeFit(16, 16, 2, 1)).toEqual({ after: 15, room: 1, over: 0 });
    expect(simTradeFit(16, 16, 1, 3)).toEqual({ after: 18, room: 0, over: 2 });
  });
  it("describes what an auto-set changed", () => {
    const a = (id: string, name: string) => ({ id, name });
    const before = [{ slot: "QB", player: a("1", "Quinn") }, { slot: "RB", player: a("2", "Hurt Harry") }];
    const after = [{ slot: "QB", player: a("1", "Quinn") }, { slot: "RB", player: a("3", "Wally Wire") }];
    const diff = simLineupDiff(before, after, 100, 107.54);
    expect(diff.swaps).toEqual([{ slot: "RB", out: "Hurt Harry", in: "Wally Wire" }]);
    expect(simAutoSetMessage(diff)).toBe("Swapped Hurt Harry for Wally Wire, +7.5 proj");
    expect(simAutoSetMessage(simLineupDiff(after, after, 100, 100))).toBe("Lineup is optimal");
    expect(simAutoSetMessage({ swaps: [{ slot: "QB", out: "A", in: "B" }, { slot: "RB", out: "C", in: "D" }], gain: null })).toBe("Made 2 lineup swaps");
  });
  it("explains why Advance is disabled", () => {
    expect(simAdvanceState({ phase: "regular_season", week: 4 }, 0)).toEqual({ label: "Wk 4 \u2192 5", blocked: false, reason: null });
    expect(simAdvanceState({ phase: "regular_season", week: 4 }, 1).reason).toBe("Fill 1 empty slot");
    expect(simAdvanceState({ phase: "regular_season", week: 4 }, 3).reason).toBe("Fill 3 empty slots");
    expect(simAdvanceState({ phase: "regular_season", week: 4, pending: { cuts_needed: 2 } }, 1).reason).toBe("Cut 2 players first");
    expect(simAdvanceState({ phase: "playoffs", week: 15 }, 0).label).toBe("Play round");
  });
});
