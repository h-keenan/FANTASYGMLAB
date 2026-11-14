import { describe, expect, it } from "vitest";

import {
  SIM_GRADES,
  simAttributeText,
  simGradeAria,
  simGradeCompare,
  simGradeFill,
  simGradeIndex,
  simGradeLegend,
  simGradeOf,
  simGradeRangeText,
  simGradeSpoken,
  simGradeText,
  simGradeTone,
} from "./simGrade";

describe("sim letter grades", () => {
  it("has 12 bands, best first, indexed A+ = 11 .. F = 0", () => {
    expect(SIM_GRADES).toHaveLength(12);
    expect(simGradeIndex("A+")).toBe(11);
    expect(simGradeIndex("F")).toBe(0);
    expect(simGradeIndex(null)).toBe(-1);
    expect(simGradeIndex("Z")).toBe(-1);
  });
  it("rides one five-tone ramp: green, cyan, gold, orange, red", () => {
    expect(["A+", "A-", "B", "C+", "D", "F"].map(simGradeTone)).toEqual(["success", "success", "accent", "gold", "warning", "danger"]);
  });
  it("shows a ? for a scouting estimate and a range for the legend", () => {
    expect(simGradeText({ grade: "B+" })).toBe("B+");
    expect(simGradeText({ grade: "B+", grade_uncertain: true })).toBe("B+?");
    expect(simGradeText({ grade: null })).toBe("—");
    expect(simGradeRangeText({ grade: "B+", grade_range: ["B-", "A-"] })).toBe("B-/A-");
    expect(simGradeRangeText({ grade: "B+" })).toBeNull();
  });
  it("speaks grades without a hyphen or a plus sign", () => {
    expect(simGradeSpoken("B-")).toBe("B minus");
    expect(simGradeSpoken("A+")).toBe("A plus");
    expect(simGradeAria({ grade: "B+", grade_uncertain: true, grade_range: ["B", "A-"] })).toBe("Grade B plus, strong starter. Scouts are unsure: B to A minus.");
    expect(simGradeAria(null)).toBe("No grade");
  });
  it("sorts best grade first, no grade last", () => {
    const rows = [{ grade: "C" as const }, { grade: null }, { grade: "A-" as const }, { grade: "B" as const }];
    expect(rows.sort(simGradeCompare).map((r) => r.grade)).toEqual(["A-", "B", "C", null]);
  });
  it("legend covers every band; fill is coarse and monotone", () => {
    expect(simGradeLegend().map((r) => r.grade)).toEqual([...SIM_GRADES]);
    const fills = SIM_GRADES.map(simGradeFill);
    expect(fills).toEqual([...fills].sort((a, b) => b - a));
    expect(simGradeFill(null)).toBe(0);
  });
  it("attribute text and the clean grade input", () => {
    expect(simAttributeText({ key: "k", label: "L", grade: "C+", uncertain: true })).toBe("C+?");
    expect(simGradeOf({ grade: null })).toBeNull();
    expect(simGradeOf({ grade: "A" })).toEqual({ grade: "A", grade_range: undefined, grade_uncertain: undefined });
  });
});
