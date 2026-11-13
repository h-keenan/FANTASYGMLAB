import { describe, expect, it } from "vitest";

import { SIM_ASSET_ALL, simAdvanceState, simEmptySlotLabels, simLineupIssues, simAutoSetMessage, simScoreboardLabel, simMatchupStatus, simMatchupMargin, simLineupDiff, simFilterGroups, simGroupByPosition, simSideSummary, simTradeFit, SIM_REVIEW_VIEWS, simReviewViewFor, simOpenKey, simParseOpen, simPreview, simSeeAllLabel, simWindow } from "./simLayout";

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
    expect(simAdvanceState({ phase: "regular_season", week: 4 }, 0)).toEqual({ label: "Wk 4 \u2192 5", blocked: false, reason: null, warning: null, confirm: null });
    expect(simAdvanceState({ phase: "regular_season", week: 4 }, 0)).toMatchObject({ blocked: false, warning: null, confirm: null });
    const one = simAdvanceState({ phase: "regular_season", week: 4 }, ["WR2"]);
    expect(one).toMatchObject({ blocked: false, reason: null });
    expect(one.confirm).toBe("WR2 is empty and will score 0 unless a healthy bench player fits. Advance anyway?");
    expect(one.warning).toContain("Claims process when you advance, before games are scored");
    expect(simAdvanceState({ phase: "regular_season", week: 4 }, 3).blocked).toBe(false);
    expect(simAdvanceState({ phase: "regular_season", week: 4, pending: { cuts_needed: 2 } }, ["WR"])).toMatchObject({ blocked: true, reason: "Cut 2 players first", confirm: null });
    expect(simEmptySlotLabels([{ slot: "QB", player: {} }, { slot: "WR", player: {} }, { slot: "WR", player: null }, { slot: "TE", player: null }])).toEqual(["WR2", "TE"]);
    expect(simAdvanceState({ phase: "playoffs", week: 15 }, 0).label).toBe("Play round");
  });
  it("warns only from the current lineup: a filled WR2 is never empty; bye/out starters are separate", () => {
    const before = [{ slot: "QB", player: { id: "q", name: "Q" } }, { slot: "WR", player: { id: "w1", name: "W1" } }, { slot: "WR", player: null }];
    expect(simLineupIssues(before, []).empty).toEqual(["WR2"]);
    const after = [before[0], before[1], { slot: "WR", player: { id: "w2", name: "Jakobi Meyers" } }];
    expect(simLineupIssues(after, []).empty).toEqual([]);
    expect(simAdvanceState({ week: 2 }, simLineupIssues(after, []).empty, []).confirm).toBeNull();
    const out = simLineupIssues(after, [{ code: "out", player_id: "w2" }, { code: "empty_slot", player_id: null }]);
    expect(out.empty).toEqual([]);
    expect(out.zero).toEqual([{ label: "WR2", name: "Jakobi Meyers", reason: "out" }]);
    expect(simAdvanceState({ week: 2 }, out.empty, out.zero).confirm).toBe("Jakobi Meyers (WR2) is out and will score 0 unless you swap him. Advance anyway?");
    expect(simAdvanceState({ week: 2 }, ["WR1"], [{ label: "RB", name: "A", reason: "bye" }]).confirm).toMatch(/WR1 is empty .* A \(RB\) is on a bye and will score 0/);
  });
  it("auto-set never says optimal while a slot is empty or a starter is on a bye/out", () => {
    const same = { swaps: [], gain: 0 };
    expect(simAutoSetMessage(same)).toBe("Lineup is optimal");
    expect(simAutoSetMessage(same, { empty: [], zero: [] })).toBe("Lineup is optimal");
    expect(simAutoSetMessage(same, { empty: ["QB"], zero: [] })).toBe("Nothing to swap. No QB on your roster to start in QB. Claim one from the Players tab.");
    expect(simAutoSetMessage(same, { empty: ["FLEX"], zero: [] })).toContain("No RB, WR or TE on your roster");
    expect(simAutoSetMessage(same, { empty: [], zero: [{ label: "WR1", name: "C. Watson", reason: "bye" }] })).toContain("C. Watson (WR1) is on a bye and no healthier player fits");
    const four = { swaps: ["RB", "WR", "TE", "K"].map((slot) => ({ slot, out: "a", in: "b" })), gain: 3.2 };
    expect(simAutoSetMessage(four, { empty: [], zero: [] })).toBe("Made 4 lineup swaps, +3.2 proj");
    expect(simAutoSetMessage(four, { empty: ["QB"], zero: [] })).toMatch(/^Made 4 lineup swaps, \+3\.2 proj\. No QB on your roster/);
  });
  it("scoreboard label never duplicates the week; matchup status and margin", () => {
    expect(simScoreboardLabel("Week 10", 10)).toBe("Week 10");
    expect(simScoreboardLabel("Semifinal", 15)).toBe("Semifinal · Week 15");
    expect(simMatchupStatus({ home_pts: 68.9, away_pts: 140.7, winner: "b" })).toEqual({ key: "final", label: "FINAL", tone: "success" });
    expect(simMatchupStatus({ home_pts: null, away_pts: null, winner: null }).key).toBe("upcoming");
    const names = { a: "Boom or Bust", b: "Flex Appeal" };
    expect(simMatchupMargin({ home: "a", away: "b", home_pts: 68.9, away_pts: 140.7 }, names)).toBe("Flex Appeal won by 71.8");
    expect(simMatchupMargin({ home: "a", away: "b", home_pts: 90, away_pts: 90 }, names)).toBe("Tie");
    expect(simMatchupMargin({ home: "a", away: "b", home_pts: null, away_pts: null }, names)).toBe("Not played yet");
  });
});
