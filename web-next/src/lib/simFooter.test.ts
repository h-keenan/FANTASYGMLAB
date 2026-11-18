import { describe, expect, it } from "vitest";

import { simAdvanceChip, simFooterTabs } from "./bottomNav";

const keys = (o: Parameters<typeof simFooterTabs>[0]) => simFooterTabs(o).map((t) => t.key);

describe("Sim footer concept A", () => {
  it("in season a short chip sits next to Home / Team / Players / Trades (no badge on tabs: the orb carries it)", () => {
    expect(keys({ chipLabel: "Play Wk 6 ▸" })).toEqual(["home", "team", "players", "trades"]);
    expect(simFooterTabs({ chipLabel: "Play Wk 6 ▸" }).every((t) => t.badge === undefined)).toBe(true);
  });
  it("a long chip takes the room of one tab", () => {
    expect(keys({ chipLabel: simAdvanceChip({ week: 6, issues: 1 }).label })).toEqual(["home", "team", "players"]);
  });
  it("offseason: Offseason / Team (the stage chips are long; Trades and League are in the orb menu)", () => {
    expect(keys({ offseason: true, chipLabel: "Start S2 2027" })).toEqual(["home", "team"]);
    expect(keys({ offseason: true, chipLabel: "Start rookie draft" })).toEqual(["home", "team"]);
  });
  it("the chip reads Play Wk N, Play round in the playoffs, and goes amber with the count when starters will score 0", () => {
    expect(simAdvanceChip({ week: 6, issues: 0 })).toEqual({ label: "Play Wk 6 ▸", warn: false });
    expect(simAdvanceChip({ phase: "playoffs", week: 15, issues: 0 }).label).toBe("Play round ▸");
    const w = simAdvanceChip({ week: 6, issues: 2 });
    expect(w.warn).toBe(true);
    expect(w.label).toContain("2");
    expect(w.label).toContain("Set lineup");
  });
});
