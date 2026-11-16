import { describe, expect, it } from "vitest";

import { simBlockable, simSingletonRuleOn, simSingletonMessage, simSingletonWarnings, simTradeSeedFor } from "@/lib/simGame";

const me = [{ id: "mk", pos: "K" }, { id: "md", pos: "DEF" }, { id: "mw", pos: "WR" }] as never[];
const them = [{ id: "tk", pos: "K" }, { id: "td", pos: "DEF" }, { id: "tw", pos: "WR" }] as never[];

describe("kicker and defense warnings", () => {
  it("they receive a second kicker (you send your K for picks)", () => {
    const w = simSingletonWarnings(me, them, ["mk"], ["pick:1"]);
    expect(w).toEqual([{ team: "them", pos: "K" }]);
    const text = simSingletonMessage(w, "The tickle monster");
    expect(text).toContain("The tickle monster already has a kicker");
    expect(text).toContain("Ask for their kicker back");
    expect(text).not.toMatch(/^You/);
  });
  it("you receive a second kicker", () => {
    const w = simSingletonWarnings(me, them, ["mw"], ["tk"]);
    expect(w).toEqual([{ team: "you", pos: "K" }]);
    expect(simSingletonMessage(w, "X")).toContain("You already have a kicker");
  });
  it("both sides, and a defense", () => {
    expect(simSingletonWarnings(me, them, ["mk", "mw"], ["tk"])).toEqual([]); // a one-for-one swap is fine
    const w = simSingletonWarnings(me, them, ["mk"], ["td", "tw"]);
    expect(w).toEqual([{ team: "them", pos: "K" }, { team: "you", pos: "DEF" }]);
    const text = simSingletonMessage(w, "Z");
    expect(text).toContain("You already have a defense");
    expect(text).toContain("Z already has a kicker");
  });
  it("shows nothing when the trade does not cause it", () => {
    expect(simSingletonWarnings(me, them, ["mw"], ["tw"])).toEqual([]);
    expect(simSingletonWarnings(me, [], ["mk"], [])).toEqual([]);
  });
  it("a kicker cannot be seeded into a trade on a save from before kd_v", () => {
    const k = { id: "tk", pos: "K" as const, owner: { type: "team", team_id: "t1" } } as never;
    expect(simTradeSeedFor(k, { kd_v: 0 })).toBeNull();
    expect(simTradeSeedFor(k, { kd_v: 1 })).toEqual({ partner: "t1", get: "tk" });
  });
});

describe("pos_v: kickers and defenses trade like any position", () => {
  it("can be blocked only with pos_v 1 (and kd_v 1)", () => {
    expect(simBlockable({ kd_v: 1, pos_v: 1 }, "K")).toBe(true);
    expect(simBlockable({ kd_v: 1, pos_v: 1 }, "DEF")).toBe(true);
    expect(simBlockable({ kd_v: 1 }, "K")).toBe(false);
    expect(simBlockable({ kd_v: 1 }, "WR")).toBe(true);
  });
  it("the one-per-team warning only exists before pos_v", () => {
    expect(simSingletonRuleOn({ kd_v: 1 })).toBe(true);
    expect(simSingletonRuleOn({ kd_v: 1, pos_v: 1 })).toBe(false);
    expect(simSingletonRuleOn({})).toBe(false);
  });
});
