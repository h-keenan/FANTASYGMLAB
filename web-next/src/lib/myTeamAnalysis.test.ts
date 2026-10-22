import { describe, expect, it } from "vitest";

import { buildRosterComposition, buildTeamAnalysisRows } from "./myTeamAnalysis";
import type { PositionGroupItem } from "./myTeamPresentation";

describe("buildRosterComposition", () => {
  it("splits value by group and always sums to 100", () => {
    const segments = buildRosterComposition([
      { key: "starters", label: "Starters", players: [{ score: 1000 }, { score: 1000 }] },
      { key: "bench", label: "Bench", players: [{ score: 1000 }] },
      { key: "ir", label: "IR", players: [{ score: 1000 }] },
      { key: "taxi", label: "Taxi", players: [] },
    ]);
    expect(segments.map((s) => s.key)).toEqual(["starters", "bench", "ir"]);
    expect(segments.map((s) => s.percent)).toEqual([50, 25, 25]);
    const thirds = buildRosterComposition([
      { key: "a", label: "A", players: [{ score: 1 }] },
      { key: "b", label: "B", players: [{ score: 1 }] },
      { key: "c", label: "C", players: [{ score: 1 }] },
    ]);
    expect(thirds.reduce((sum, s) => sum + s.percent, 0)).toBe(100);
  });

  it("returns nothing when no group has value", () => {
    expect(buildRosterComposition([{ key: "starters", label: "Starters", players: [{ score: null }] }])).toEqual([]);
  });
});

describe("buildTeamAnalysisRows", () => {
  const item = (position: string, label: string): PositionGroupItem => ({
    position,
    label,
    tone: "strength",
    contextSuffix: "",
    body: `${position} body`,
  });

  it("orders QB/RB/WR/TE first and maps labels to short statuses", () => {
    const rows = buildTeamAnalysisRows([item("TE", "Covered"), item("LB", "Thin"), item("QB", "Upgrade room"), item("RB", "Strength")]);
    expect(rows.map((r) => r.position)).toEqual(["QB", "RB", "TE", "LB"]);
    expect(rows[0]).toMatchObject({ status: "Upgrade opportunity", tone: "warning" });
    expect(rows[1]).toMatchObject({ status: "Strength", tone: "success" });
  });
});
