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

describe("peek sheet height (computed from content)", () => {
  it("fits header + pill row + one content line, clamped to 40-70% of the screen", async () => {
    const { peekSheetHeight, peekShowsTabs, PEEK_FIRST_LINE_PX } = await import("./playerAnatomy");
    expect(peekSheetHeight({ anchorBottom: 400, viewportH: 844, bottomInset: 0 })).toBe(400 + PEEK_FIRST_LINE_PX);
    expect(peekSheetHeight({ anchorBottom: 210, viewportH: 844 })).toBe(Math.round(844 * 0.4)); // short header: never a sliver
    expect(peekSheetHeight({ anchorBottom: 900, viewportH: 640 })).toBe(Math.round(640 * 0.7)); // never right under the page header
    expect(peekSheetHeight({ anchorBottom: 400, viewportH: 844, bottomInset: 34 })).toBe(486);
    // the 390x844 and 360x640 compact layouts (measured in pqv_peek_geometry.mjs) keep the pill row inside the peek
    for (const [anchor, vh] of [[210, 844], [187, 640]] as const) expect(peekShowsTabs(anchor, peekSheetHeight({ anchorBottom: anchor, viewportH: vh }))).toBe(true);
    expect(peekShowsTabs(300, 250)).toBe(false);
  });
});
