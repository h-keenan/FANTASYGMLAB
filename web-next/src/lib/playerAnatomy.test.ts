import { describe, expect, it } from "vitest";
import { barFractions, fairnessMeter, tradeEdge, METER_BAND, nextOpenId, nextSheetSnap, orderPlayerSheetTabs, playerInitials, playerRowModel } from "./playerAnatomy";

const chase = { id: "7564", name: "Ja'Marr Chase", team: "CIN", age: 25 };

describe("playerAnatomy", () => {
  it("initials", () => {
    expect(playerInitials("Ja'Marr Chase")).toBe("JC");
    expect(playerInitials("Odell Beckham Jr.")).toBe("OB");
    expect(playerInitials("")).toBe("?");
  });
  it("desk shows proj, value and trend", () => {
    const m = playerRowModel({ player: chase, mode: "desk", proj: 19.8, value: 92, trend: 4, bye: 12 });
    expect(m.meta).toEqual(["CIN", "Age 25", "BYE 12"]);
    expect(m.trailing?.label).toBe("PROJ");
    expect(m.facts.map((f) => f.key)).toEqual(["proj", "value", "trend"]);
  });
  it("sim never exposes value or overall", () => {
    const m = playerRowModel({ player: chase, mode: "sim", grade: "A-", adp: 3.4, proj: 312, value: 92, ovr: 88, trend: 3 });
    expect(m.facts.map((f) => f.key)).toEqual(["grade", "adp", "proj"]);
    expect(JSON.stringify(m)).not.toMatch(/VALUE|OVR|92|88/);
    expect(m.trailing?.value).toBe("A-");
  });
  it("one open at a time", () => {
    expect(nextOpenId(null, "a")).toBe("a");
    expect(nextOpenId("a", "b")).toBe("b");
    expect(nextOpenId("b", "b")).toBeNull();
  });
  it("fairness meter math: clamped band, direction, labels", () => {
    expect(fairnessMeter(100, 100).label).toBe("Even");
    expect(fairnessMeter(0, 0).position).toBe(0.5);
    expect(tradeEdge(100, 200)).toBe(0.5);
    expect(tradeEdge(200, 100)).toBe(-0.5);
    // 10% loss is a quarter of the way to the end on a 25% band: 0.5 - 0.2
    const small = fairnessMeter(1000, 900);
    expect(small.position).toBeCloseTo(0.5 - (0.1 / METER_BAND) * 0.5, 5);
    expect(small.label).toBe("You lose by ~10%");
    expect(small.tone).toBe("danger");
    expect(fairnessMeter(1000, 1120).label).toBe("You win by ~11%");
    expect(fairnessMeter(1000, 1120).tone).toBe("success");
    expect(fairnessMeter(1000, 2000).position).toBe(1);
    expect(fairnessMeter(2000, 1000).position).toBe(0);
    expect(fairnessMeter(1000, 1040).label).toBe("Slight edge to you");
    expect(fairnessMeter(1040, 1000).label).toBe("Slight edge to them");
    expect(fairnessMeter(1000, 1010).tone).toBe("muted");
    expect(fairnessMeter(1000, 900).description).toMatch(/lose/);
  });
  it("server net value wins over asset sums that miss pick values", () => {
    // players alone say -40% but the server counts the pick: net -583 on 3575 sent
    const m = fairnessMeter(3575, 2159, "desk", -583);
    expect(m.edge).toBeCloseTo(-583 / 3575, 5);
    expect(m.tone).toBe("danger");
  });
  it("sim meter uses plain words, coarse steps and hides the value", () => {
    expect(fairnessMeter(100, 100, "sim").label).toBe("About even");
    expect(fairnessMeter(100, 200, "sim").label).toBe("In your favor");
    expect(fairnessMeter(1000, 1100, "sim").label).toBe("Slightly in your favor");
    expect(fairnessMeter(1100, 1000, "sim").label).toBe("Slightly in their favor");
    const a = fairnessMeter(1000, 1160, "sim");
    const b = fairnessMeter(1000, 1170, "sim");
    expect(a.position).toBe(b.position);
    expect(a.edge).toBe(0);
    expect(`${a.label}${a.description}`).not.toMatch(/\d/);
  });
  it("bar fractions", () => {
    expect(barFractions([10, 5, null])).toEqual([1, 0.5, 0]);
  });
  it("snap and tab order", () => {
    expect(nextSheetSnap("peek", -80)).toBe("full");
    expect(nextSheetSnap("full", 80)).toBe("peek");
    expect(nextSheetSnap("peek", -10)).toBe("peek");
    expect(orderPlayerSheetTabs([{ key: "outlook" }, { key: "overview" }, { key: "stats" }]).map((t) => t.key)).toEqual(["overview", "stats", "outlook"]);
  });
});
