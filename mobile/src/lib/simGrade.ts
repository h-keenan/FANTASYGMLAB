/**
 * Letter grades for the Fantasy Sim (docs/ui-patterns.md, "Fantasy Sim letter grades"). Pure and import-free, byte-identical
 * twin of mobile/src/lib/simGrade.ts.
 *
 * The sim never shows a numeric overall: sort by it and you have the model's hidden rating. It shows Madden / 2K style
 * grades instead: 12 coarse bands from a noisy read of the rating (server: modules/sim/game_grades.py), plus position
 * attribute grades in the player quick view. Rookies carry a range and a "?".
 */

export const SIM_GRADES = ["A+", "A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D+", "D", "F"] as const;
export type SimGradeLetter = (typeof SIM_GRADES)[number];

/** One position attribute grade (player detail). `uncertain` = a scouting estimate (rookies). */
export interface SimAttributeGrade {
  key: string;
  label: string;
  grade: SimGradeLetter;
  uncertain?: boolean;
}

/** The five semantic tones of the ramp: green, cyan, gold, orange, red (existing tokens only, no new colour). */
export type SimGradeTone = "success" | "accent" | "gold" | "warning" | "danger";

/** Rank of a grade, 11 = A+ ... 0 = F; -1 for no grade. */
export function simGradeIndex(grade: string | null | undefined): number {
  const i = grade ? SIM_GRADES.indexOf(grade as SimGradeLetter) : -1;
  return i < 0 ? -1 : SIM_GRADES.length - 1 - i;
}

export function simGradeTone(grade: string | null | undefined): SimGradeTone {
  const letter = grade?.charAt(0);
  return letter === "A" ? "success" : letter === "B" ? "accent" : letter === "C" ? "gold" : letter === "D" ? "warning" : "danger";
}

const MEANING: Record<SimGradeLetter, string> = {
  "A+": "Elite. A top-of-position difference maker.",
  A: "Star. A clear WR1 / RB1 type.",
  "A-": "Very good starter.",
  "B+": "Strong starter.",
  B: "Solid starter.",
  "B-": "Fringe starter.",
  "C+": "Flex or bench upside.",
  C: "Depth.",
  "C-": "Deep bench.",
  "D+": "Roster filler.",
  D: "Waiver wire.",
  F: "Below replacement.",
};

export function simGradeMeaning(grade: string | null | undefined): string {
  return grade && grade in MEANING ? MEANING[grade as SimGradeLetter] : "";
}

/** Legend rows, best first. */
export function simGradeLegend(): { grade: SimGradeLetter; meaning: string }[] {
  return SIM_GRADES.map((grade) => ({ grade, meaning: MEANING[grade] }));
}

/** "B-" -> "B minus" so a screen reader does not read a hyphen. */
export function simGradeSpoken(grade: string): string {
  return grade.replace("+", " plus").replace("-", " minus");
}

export interface SimGradeInput {
  grade?: SimGradeLetter | null;
  grade_range?: [SimGradeLetter, SimGradeLetter] | null;
  grade_uncertain?: boolean;
}

/** The text a badge shows: the letter, with "?" when it is only a scouting estimate. */
export function simGradeText(p: SimGradeInput | null | undefined): string {
  if (!p?.grade) return "—";
  return p.grade_uncertain ? `${p.grade}?` : p.grade;
}

/** "B-/B+" for an uncertain grade with a range, else null. */
export function simGradeRangeText(p: SimGradeInput | null | undefined): string | null {
  const r = p?.grade_range;
  return r ? `${r[0]}/${r[1]}` : null;
}

/** The accessible name and tooltip: "Grade B plus, strong starter. Scouts are unsure: B to A minus." */
export function simGradeAria(p: SimGradeInput | null | undefined): string {
  if (!p?.grade) return "No grade";
  const base = `Grade ${simGradeSpoken(p.grade)}, ${simGradeMeaning(p.grade).replace(/\.$/, "").toLowerCase()}`;
  if (!p.grade_uncertain) return base;
  const r = p.grade_range;
  return r ? `${base}. Scouts are unsure: ${simGradeSpoken(r[0])} to ${simGradeSpoken(r[1])}.` : `${base}. Scouts are unsure.`;
}

/** Sort comparator: best grade first, no grade last. */
export function simGradeCompare(a: SimGradeInput | null | undefined, b: SimGradeInput | null | undefined): number {
  return simGradeIndex(b?.grade) - simGradeIndex(a?.grade);
}

/** Attribute grades with a "?" where the scouts are guessing. */
export function simAttributeText(a: SimAttributeGrade): string {
  return a.uncertain ? `${a.grade}?` : a.grade;
}

/** 0-100 fill for a GradeBar (F = 8, A+ = 100): coarse on purpose. */
export function simGradeFill(grade: string | null | undefined): number {
  const i = simGradeIndex(grade);
  return i < 0 ? 0 : Math.round(8 + (i / 11) * 92);
}

/** The grade fields of a player row as a clean `SimGradeInput` (null when he has none). */
export function simGradeOf(p: SimGradeInput | null | undefined): SimGradeInput | null {
  return p?.grade ? { grade: p.grade, grade_range: p.grade_range, grade_uncertain: p.grade_uncertain } : null;
}
