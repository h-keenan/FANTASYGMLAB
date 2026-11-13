import { describe, expect, it } from "vitest";

import {
  EMPTY_FILTERS,
  activeFilterCount,
  applyLabel,
  conditionsFor,
  filterSheetItems,
  filterSummary,
  groupSheetItems,
  initialSheetState,
  itemKey,
  positionsFor,
  selectedItems,
  sheetReducer,
  summarizeItems,
  type SheetAction,
  type SheetItem,
  type SheetState,
} from "./tradeSheetPicker";

function player(id: string, over: Partial<SheetItem> = {}): SheetItem {
  return { key: itemKey("player", id), kind: "player", id, label: `Player ${id}`, position: "RB", team: "KC", age: 25, value: 1000, conditions: ["healthy"], ...over };
}
function pick(id: string, over: Partial<SheetItem> = {}): SheetItem {
  return { key: itemKey("pick", id), kind: "pick", id, label: `Pick ${id}`, position: null, team: null, age: null, value: 500, conditions: [], group: "2027 picks", ...over };
}

const run = (state: SheetState, ...actions: SheetAction[]) => actions.reduce(sheetReducer, state);

describe("conditionsFor", () => {
  it("tags healthy, injured, bye and rookie", () => {
    expect(conditionsFor({ injuryStatus: null, age: 27 })).toEqual(["healthy"]);
    expect(conditionsFor({ injuryStatus: "Questionable", age: 27 })).toEqual(["injured"]);
    expect(conditionsFor({ status: "Bye", age: 27 })).toEqual(["bye"]);
    expect(conditionsFor({ injuryStatus: "Out", age: 21 })).toEqual(["injured", "rookie"]);
    expect(conditionsFor({ age: 30, rookie: true })).toContain("rookie");
    expect(conditionsFor({ injuryStatus: "Active", age: 25 })).toEqual(["healthy"]);
  });
});

describe("filterSheetItems", () => {
  const items = [
    player("1", { position: "RB", conditions: ["healthy"], label: "Alpha Runner" }),
    player("2", { position: "WR", conditions: ["injured"], label: "Beta Wideout" }),
    player("3", { position: "WR", conditions: ["healthy", "rookie"], label: "Gamma Wideout" }),
    pick("a"),
  ];
  const base = { tab: "players" as const, query: "", filters: EMPTY_FILTERS };

  it("separates players and picks by tab", () => {
    expect(filterSheetItems(items, base).map((i) => i.id)).toEqual(["1", "2", "3"]);
    expect(filterSheetItems(items, { ...base, tab: "picks" }).map((i) => i.id)).toEqual(["a"]);
  });
  it("ORs within a filter group and ANDs across groups", () => {
    const wr = { positions: ["WR"], conditions: [] };
    expect(filterSheetItems(items, { ...base, filters: wr }).map((i) => i.id)).toEqual(["2", "3"]);
    expect(filterSheetItems(items, { ...base, filters: { positions: ["WR"], conditions: ["injured", "rookie"] } }).map((i) => i.id)).toEqual(["2", "3"]);
    expect(filterSheetItems(items, { ...base, filters: { positions: ["WR", "RB"], conditions: ["healthy"] } }).map((i) => i.id)).toEqual(["1", "3"]);
    expect(filterSheetItems(items, { ...base, filters: { positions: ["RB"], conditions: ["injured"] } })).toEqual([]);
  });
  it("searches name, team and position, and leaves picks out of player filters", () => {
    expect(filterSheetItems(items, { ...base, query: "gamma" }).map((i) => i.id)).toEqual(["3"]);
    expect(filterSheetItems(items, { tab: "picks", query: "", filters: { positions: ["QB"], conditions: ["injured"] } }).map((i) => i.id)).toEqual(["a"]);
  });
});

describe("sheetReducer", () => {
  it("toggles selection in pick order and removes", () => {
    let s = initialSheetState();
    s = run(s, { type: "toggle", key: "player:1" }, { type: "toggle", key: "pick:a" }, { type: "toggle", key: "player:2" });
    expect(s.selected).toEqual(["player:1", "pick:a", "player:2"]);
    s = run(s, { type: "toggle", key: "pick:a" });
    expect(s.selected).toEqual(["player:1", "player:2"]);
    s = run(s, { type: "remove", key: "player:1" });
    expect(s.selected).toEqual(["player:2"]);
    expect(run(s, { type: "clearSelection" }).selected).toEqual([]);
  });
  it("enforces the per-side max on add but always allows removing", () => {
    let s = run(initialSheetState(), { type: "toggle", key: "a", max: 2 }, { type: "toggle", key: "b", max: 2 }, { type: "toggle", key: "c", max: 2 });
    expect(s.selected).toEqual(["a", "b"]);
    s = run(s, { type: "toggle", key: "a", max: 2 });
    expect(s.selected).toEqual(["b"]);
  });
  it("keeps filters as a draft until Apply, and Cancel discards the draft", () => {
    let s = run(initialSheetState(), { type: "openFilters" }, { type: "draftPosition", position: "RB" }, { type: "draftCondition", condition: "injured" });
    expect(s.filters).toEqual(EMPTY_FILTERS);
    expect(s.draft).toEqual({ positions: ["RB"], conditions: ["injured"] });
    s = run(s, { type: "closeFilters" });
    expect(s.draft).toBeNull();
    expect(s.filters).toEqual(EMPTY_FILTERS);
    s = run(s, { type: "openFilters" }, { type: "draftPosition", position: "WR" }, { type: "applyFilters" });
    expect(s.filters).toEqual({ positions: ["WR"], conditions: [] });
    expect(s.draft).toBeNull();
  });
  it("re-opening starts from the applied filters; chips toggle off; Clear empties the draft", () => {
    let s = run(initialSheetState(), { type: "openFilters" }, { type: "draftPosition", position: "WR" }, { type: "applyFilters" });
    s = run(s, { type: "openFilters" });
    expect(s.draft?.positions).toEqual(["WR"]);
    s = run(s, { type: "draftPosition", position: "WR" });
    expect(s.draft?.positions).toEqual([]);
    s = run(s, { type: "draftPosition", position: "TE" }, { type: "clearDraft" });
    expect(s.draft).toEqual(EMPTY_FILTERS);
    expect(s.filters.positions).toEqual(["WR"]);
    s = run(s, { type: "applyFilters" });
    expect(s.filters).toEqual(EMPTY_FILTERS);
  });
  it("ignores draft actions while the panel is closed, and keeps selection across tab/query changes", () => {
    let s = run(initialSheetState(["player:1"]), { type: "draftPosition", position: "RB" }, { type: "applyFilters" });
    expect(s.filters).toEqual(EMPTY_FILTERS);
    s = run(s, { type: "tab", tab: "picks" }, { type: "query", query: "x" });
    expect(s.selected).toEqual(["player:1"]);
    expect(s.tab).toBe("picks");
  });
  it("switching tab closes an open filter panel", () => {
    expect(run(initialSheetState(), { type: "openFilters" }, { type: "tab", tab: "picks" }).draft).toBeNull();
  });
});

describe("summaries", () => {
  it("lists selected items in pick order, drops missing keys, and totals value", () => {
    const items = [player("1", { value: 100 }), player("2", { value: 50 }), pick("a", { value: 25 })];
    const chosen = selectedItems(items, ["pick:a", "player:9", "player:1"]);
    expect(chosen.map((i) => i.key)).toEqual(["pick:a", "player:1"]);
    expect(summarizeItems(chosen)).toEqual({ count: 2, players: 1, picks: 1, total: 125 });
  });
  it("labels the footer button", () => {
    expect(applyLabel([], [])).toBe("Done");
    expect(applyLabel(["a", "b"], [])).toBe("Add 2 to trade");
    expect(applyLabel(["a"], ["a", "b"])).toBe("Update trade (1)");
    expect(applyLabel([], ["a"])).toBe("Clear this side");
    expect(applyLabel(["b", "a"], ["a", "b"])).toBe("Done");
  });
  it("describes filters", () => {
    expect(filterSummary({ positions: ["RB", "WR"], conditions: ["injured"] })).toBe("RB, WR · Injured");
    expect(activeFilterCount({ positions: ["RB"], conditions: ["bye", "rookie"] })).toBe(3);
  });
  it("orders positions football-style and groups picks by season", () => {
    expect(positionsFor([player("1", { position: "WR" }), player("2", { position: "QB" }), player("3", { position: "DL" }), player("4", { position: "zz" })])).toEqual(["QB", "WR", "DL", "ZZ"]);
    const groups = groupSheetItems([pick("a"), pick("b", { group: "2028 picks" }), pick("c")]);
    expect(groups.map((g) => [g.label, g.items.length])).toEqual([["2027 picks", 2], ["2028 picks", 1]]);
  });
});
