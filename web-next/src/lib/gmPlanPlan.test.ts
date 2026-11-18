import { describe, expect, it } from "vitest";

import { buildPlanSteps, buildPlanWhy, ordinal, planFacts, planStatTiles } from "./gmPlanPlan";

const SNAP = [
  { key: "power", value: "11 of 12" },
  { key: "capital", value: "1 of 12" },
  { key: "odds", value: "0%" },
  { key: "record", value: "3 - 7" },
];

describe("gmPlanPlan", () => {
  it("orders ordinals", () => {
    expect([1, 2, 3, 11, 12, 13, 21, 22].map(ordinal)).toEqual(["1st", "2nd", "3rd", "11th", "12th", "13th", "21st", "22nd"]);
  });

  it("builds the four tiles with value and note split", () => {
    const tiles = planStatTiles(SNAP);
    expect(tiles.map((t) => [t.label, t.value, t.note])).toEqual([
      ["This season", "11th", "of 12"],
      ["Draft capital", "1st", "of 12"],
      ["Playoff odds", "0%", undefined],
      ["Record", "3-7", undefined],
    ]);
    expect(planStatTiles([])).toEqual([]);
  });

  it("builds stance steps with the capital step and signal areas only", () => {
    const steps = buildPlanSteps({
      stance: "rebuilding",
      tradeCount: 2,
      partners: ["The Hospital", "Just Win"],
      topConfidence: "High",
      capital: planFacts(SNAP).capital,
      areas: [
        { key: "a", title: "Roster Construction", framing: "Thin at WR", count: 1, hasSignal: true },
        { key: "b", title: "Where You Stand", framing: "", count: 0, hasSignal: false },
      ],
    });
    expect(steps.map((s) => s.title)).toEqual(["Sell aging vets for picks", "Stack draft capital", "Roster Construction"]);
    expect(steps[0]).toMatchObject({ kind: "trades", summary: "2 ideas: The Hospital and Just Win" });
    expect(steps[1].chip).toEqual({ label: "1st", tone: "success" });
  });

  it("explains the stance and is null without one", () => {
    const why = buildPlanWhy("rebuilding", planFacts(SNAP), 14);
    expect(why?.title).toBe("Why rebuild");
    expect(why?.headline).toBe("0% playoff odds, 3-7: sell now, buy youth");
    expect(why?.bullets).toHaveLength(3);
    expect(buildPlanWhy("", planFacts(SNAP), null)).toBeNull();
  });
});
