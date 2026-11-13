import { describe, expect, it } from "vitest";

import type { SimToWeek } from "./simGame";
import { simToCanForce, simToFixLabel, simToFixTab, simToHeadline, simToProgressLabel, simToRecordLine, simToWeekLine } from "./simTo";

const wk = (week: number, over: Partial<SimToWeek> = {}): SimToWeek => ({ week, kind: "regular", result: "w", your_pts: 112.4, opp_pts: 98.66, opponent: "Rats", auto_filled: [], ...over });

describe("sim to presentation", () => {
  it("headline names the weeks", () => {
    expect(simToHeadline(0, null)).toBe("Nothing simulated");
    expect(simToHeadline(1, { weeks: [wk(3)] })).toBe("Simmed Week 3");
    expect(simToHeadline(4, { weeks: [wk(3), wk(4), wk(5), wk(6)] })).toBe("Simmed 4 weeks (Weeks 3-6)");
    expect(simToHeadline(2, { weeks: [wk(15, { kind: "playoff" }), wk(16, { kind: "playoff" })] })).toBe("Played 2 playoff rounds");
  });
  it("week lines and record line", () => {
    expect(simToWeekLine(wk(3))).toBe("W 112.4-98.7 vs Rats");
    expect(simToWeekLine(wk(4, { result: "bye" }))).toBe("Bye week");
    expect(simToWeekLine(wk(4, { result: null }))).toBe("No game");
    expect(simToRecordLine({ record: { before: "2-1", after: "4-2" }, rank: { before: 4, after: 2 } })).toBe("2-1 to 4-2 · #4 to #2");
    expect(simToRecordLine({ record: { before: "2-1", after: "2-1" }, rank: { before: 4, after: 4 } })).toBe("2-1 · #4");
  });
  it("fix buttons, forcing and tabs follow the stop", () => {
    expect(simToFixLabel({ fix: "lineup", code: "starter_out" })).toBe("Fix lineup");
    expect(simToFixLabel({ fix: "lineup", code: "empty_slot" })).toBe("Fill the slot");
    expect(simToFixLabel({ fix: "roster", code: "roster_over_limit" })).toBe("Make cuts");
    expect(simToFixLabel({ fix: "inbox", code: "trade_offers" })).toBe("Answer offers");
    expect(simToFixLabel({ fix: null, code: "time_budget" })).toBeNull();
    expect(["starter_out", "starter_bye", "empty_slot", "trade_offers"].every((c) => simToCanForce({ code: c as never }))).toBe(true);
    expect(simToCanForce({ code: "roster_over_limit" })).toBe(false);
    expect(simToCanForce({ code: "premium_required" })).toBe(false);
    expect([simToFixTab({ fix: "lineup" }), simToFixTab({ fix: "inbox" }), simToFixTab({ fix: "premium" })]).toEqual(["team", "trades", null]);
    expect(simToProgressLabel("Trade deadline (week 10)")).toBe("Simulating: trade deadline (week 10)...");
  });
});
