import { describe, expect, it } from "vitest";

import type { SimToSummary } from "./simGame";
import { SIM_TO_DEFAULT_PREFS, SIM_TO_STOP_ROWS, simToCanForce, simToFixLabel, simToParsePrefs, simToReadout, simToRemaining, simToSerializePrefs, simToStopCount } from "./simTo";

const summary = (over: Partial<SimToSummary> = {}): SimToSummary => ({
  weeks: [], record: { before: "0-0", after: "2-0" }, rank: { before: 1, after: 1 }, pf: 200, injuries: [], claims: [], ai_trades: 0, standings: [], champion: null, season_complete: false, ...over,
});

describe("sim to toggles", () => {
  it("defaults: auto-set on and every stop on; one row per stop", () => {
    expect(SIM_TO_DEFAULT_PREFS.autoSet).toBe(true);
    expect(Object.values(SIM_TO_DEFAULT_PREFS.stops).every(Boolean)).toBe(true);
    expect(SIM_TO_STOP_ROWS.map((r) => r.key).sort()).toEqual(Object.keys(SIM_TO_DEFAULT_PREFS.stops).sort());
    expect(simToParsePrefs(null)).toEqual(SIM_TO_DEFAULT_PREFS);
  });
  it("persisted choices round-trip and junk falls back per field", () => {
    const prefs = { autoSet: false, stops: { ...SIM_TO_DEFAULT_PREFS.stops, offers: false, deadline: false } };
    expect(simToParsePrefs(simToSerializePrefs(prefs))).toEqual(prefs);
    expect(simToStopCount(prefs.stops)).toBe(3);
    expect(simToParsePrefs("{nope")).toEqual(SIM_TO_DEFAULT_PREFS);
    expect(simToParsePrefs(JSON.stringify({ autoSet: "yes", stops: { offers: 0, injuries: false } })).stops).toEqual({ ...SIM_TO_DEFAULT_PREFS.stops, injuries: false });
  });
  it("new stop codes get a fix button and can be simmed past", () => {
    expect(simToFixLabel({ fix: "inbox", code: "trade_deadline" })).toBe("Open trades");
    expect(simToFixLabel({ fix: "roster", code: "waiver_issue" })).toBe("Fix claims");
    expect(simToFixLabel({ fix: "lineup", code: "starter_injured" })).toBe("Review lineup");
    expect(["starter_injured", "trade_deadline", "waiver_issue"].every((c) => simToCanForce({ code: c as never }))).toBe(true);
  });
  it("keep simming only plays the weeks that are left", () => {
    expect(simToRemaining({ id: "weeks", weeks: 4, label: "4 weeks" }, 1).weeks).toBe(3);
    expect(simToRemaining({ id: "weeks", weeks: 4, label: "4 weeks" }, 9).weeks).toBe(1);
    expect(simToRemaining({ id: "season_end", label: "x" }, 3)).toEqual({ id: "season_end", label: "x" });
  });
  it("the readout names lineup changes, offers, roster overage and injuries", () => {
    expect(simToReadout(summary())).toEqual([]);
    expect(simToReadout(summary({ auto_set: true, lineup_changes: [] }))).toEqual(["Lineup auto-set: no changes needed."]);
    const lines = simToReadout(summary({
      auto_set: true,
      lineup_changes: [{ week: 1, slot: "RB", out: "A", in: "B" }, { week: 2, slot: "WR", out: "C", in: "D" }],
      offers_pending: 2, offers_new: 1, roster: { size: 20, limit: 18, over: 2 },
      injuries: [{ week: 2, player: { id: "1", name: "X", pos: "RB" }, weeks: 3 }],
    }));
    expect(lines).toEqual([
      "Lineup auto-set: 2 changes over 2 weeks.",
      "2 trade offers waiting (1 new).",
      "Over the limit by 2: cut or trade to add players.",
      "1 injury to your players.",
    ]);
  });
});
