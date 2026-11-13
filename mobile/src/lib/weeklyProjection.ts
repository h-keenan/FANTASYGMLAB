// Shared (web + mobile twin): the data side of the weekly points chart's optional
// projection overlay. The chart itself stays ONE component per platform; this module
// only turns "actual points so far" + "per-week projection" into plot rows.
//
// Used by the Fantasy Sim player sheet (actual points so far this sim season + the
// rest-of-season projection band) through the same chart the real Player Quick View uses.

export interface WeeklyProjectionPoint {
  week: number;
  mean: number;
  floor: number;
  ceiling: number;
}

export interface WeeklyActualPoint {
  week: number;
  points: number | null;
}

export interface WeeklyChartRow {
  week: number;
  actual: number | null;
  mean: number | null;
  floor: number | null;
  ceiling: number | null;
}

/** One row per week from the first to the last week either series covers. */
export function buildWeeklyChartRows(actual: readonly WeeklyActualPoint[], projection: readonly WeeklyProjectionPoint[] | null | undefined): WeeklyChartRow[] {
  const weeks = [...actual.map((a) => a.week), ...(projection ?? []).map((p) => p.week)];
  if (weeks.length === 0) return [];
  const first = Math.min(...weeks);
  const last = Math.max(...weeks);
  const a = new Map(actual.map((x) => [x.week, x.points]));
  const p = new Map((projection ?? []).map((x) => [x.week, x]));
  const rows: WeeklyChartRow[] = [];
  for (let week = first; week <= last; week += 1) {
    const proj = p.get(week);
    rows.push({
      week,
      actual: a.get(week) ?? null,
      mean: proj ? proj.mean : null,
      floor: proj ? proj.floor : null,
      ceiling: proj ? proj.ceiling : null,
    });
  }
  return rows;
}

/** True when the projection is the same number every week (so a chart band or a week-by-week list says nothing). */
export function isFlatProjection(projection: readonly Pick<WeeklyProjectionPoint, "mean" | "floor" | "ceiling">[]): boolean {
  if (projection.length <= 1) return true;
  const key = (p: Pick<WeeklyProjectionPoint, "mean" | "floor" | "ceiling">) => `${p.mean}|${p.floor}|${p.ceiling}`;
  const first = key(projection[0]);
  return projection.every((p) => key(p) === first);
}
