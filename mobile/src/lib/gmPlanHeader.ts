/**
 * GM Plan header chips: posture / window / needs, three at-a-glance numbers above the stance picker.
 * Pure and import-free, byte-identical twin of mobile/src/lib/gmPlanHeader.ts. Every value is a real field the page already
 * has (the declared stance, the trade-deadline week, the focus-area signals); a chip with no data says so plainly.
 */

export type PlanHeaderStance = "rebuilding" | "competing" | "balanced" | "";

export interface PlanHeaderChip {
  key: "posture" | "window" | "needs";
  label: string;
  value: string;
  note?: string;
}

type AreaItemLike = { injury_need_positions?: readonly string[]; relative_weak_spot?: boolean | null };
type AreaLike = { items: readonly object[] };

const POSTURE_VALUE: Record<string, string> = { rebuilding: "Rebuild", competing: "Compete", balanced: "Balanced" };

/** Needs = injured-starter positions with no bench cover, plus ranked categories flagged as a relative weak spot. */
export function countPlanNeeds(areas: readonly AreaLike[]): number {
  let needs = 0;
  for (const area of areas) {
    for (const raw of area.items) {
      const item = raw as AreaItemLike;
      if (item.injury_need_positions) needs += item.injury_need_positions.length;
      else if (item.relative_weak_spot) needs += 1;
    }
  }
  return needs;
}

export function planHeaderChips(input: {
  stance: PlanHeaderStance;
  deadlineWeek: number | null;
  pastDeadline: boolean;
  needs: number;
}): PlanHeaderChip[] {
  const { stance, deadlineWeek, pastDeadline, needs } = input;
  return [
    { key: "posture", label: "Stance", value: POSTURE_VALUE[stance] ?? "Not set" },
    {
      key: "window",
      label: "Window",
      value: deadlineWeek !== null ? `Wk ${deadlineWeek}` : pastDeadline ? "Closed" : "Open",
      note: deadlineWeek !== null ? "trade deadline" : pastDeadline ? "deadline passed" : undefined,
    },
    { key: "needs", label: "Needs", value: String(needs), note: "to address" },
  ];
}
