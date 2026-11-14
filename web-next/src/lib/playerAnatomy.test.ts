import { describe, expect, it } from "vitest";
import { barFractions, fairnessMeter, nextOpenId, nextSheetSnap, orderPlayerSheetTabs, playerInitials, playerRowModel } from "./playerAnatomy";

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
  it("fairness uses plain words in sim", () => {
    expect(fairnessMeter(100, 100).label).toBe("Fair");
    expect(fairnessMeter(100, 200, "sim").label).toBe("A better deal for you");
    expect(fairnessMeter(200, 100).tone).toBe("danger");
    expect(fairnessMeter(0, 0).position).toBe(0.5);
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
