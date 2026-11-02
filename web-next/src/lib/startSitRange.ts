/** Start/sit floor and ceiling, from modules/start_sit_range.py. Mirrors
 * mobile/src/lib/startSitRange.ts. `low`/`high` are a typical-week range from
 * the player's projection, never a percentile or a boom/bust probability. */

export interface StartSitRangeRow {
  name: string;
  projected: number;
  low: number;
  high: number;
}

export interface StartSitStance {
  kind: "underdog" | "favorite" | "toss_up";
  win_pct: number;
}

export interface StartSitLean<Side extends string> {
  kind: "ceiling" | "floor";
  favors: Side;
  /** Plain-English reason, already built from the numbers shown. */
  why: string;
}

/** On a suggested move: `start` is the player to start, `over` the one he replaces. */
export interface MoveRange {
  start: StartSitRangeRow | null;
  over: StartSitRangeRow | null;
  stance: StartSitStance | null;
  lean: StartSitLean<"start" | "over"> | null;
}

/** On a swap-sheet candidate: `candidate` vs the `current` occupant. */
export interface CandidateCompare {
  candidate: StartSitRangeRow | null;
  current: StartSitRangeRow | null;
  stance: StartSitStance | null;
  lean: StartSitLean<"candidate" | "current"> | null;
}

export const RANGE_CAPTION =
  "Low and High are a typical-week range from recent games, not a guaranteed floor or ceiling.";

export function leanLabel(kind: "ceiling" | "floor"): string {
  return kind === "ceiling" ? "Ceiling play" : "Floor play";
}

export function formatPoints(value: number): string {
  return value.toFixed(1);
}

export interface RangeDisplayRow {
  key: string;
  label: string;
  name: string;
  range: StartSitRangeRow;
  favored: boolean;
}

/** The rows to render, in order, skipping any side with no real range. */
export function rangeDisplayRows(
  rows: Array<{ key: string; label: string; range: StartSitRangeRow | null }>,
  favoredKey: string | null,
): RangeDisplayRow[] {
  return rows
    .filter((row): row is { key: string; label: string; range: StartSitRangeRow } => row.range != null)
    .map((row) => ({ ...row, name: row.range.name, favored: row.key === favoredKey }));
}
