/**
 * Pure logic for the Player Quick View's Depth chart and Injury history sections. Import-free, byte-identical twin
 * of mobile/src/lib/playerDepthInjury.ts. The shapes are what GET /v1/players/{id}/depth-chart and
 * /injury-history return (modules/player_depth_chart.py, modules/player_injury_record.py). The depth chart is
 * plain data (entries + labels) so the same section can draw a real NFL team's chart or a simulated one.
 */

import type { CompactPart } from "./compactModule";

export interface DepthChartEntry {
  player_id: string;
  name: string;
  position?: string | null;
  team?: string | null;
  /** The team's own order at this slot (1 = starter); not always contiguous. */
  order: number;
  status?: string | null;
  injury_status?: string | null;
  is_self: boolean;
  /** Spots moved since the last weekly reading: positive = up. null = no prior reading. */
  change?: number | null;
}

export interface DepthChartData {
  ok: boolean;
  player_id?: string;
  team: string | null;
  slot: string | null;
  slot_label: string | null;
  self_order: number | null;
  entries: DepthChartEntry[];
  total: number;
  reason?: string;
}

export interface InjuryStint {
  start_week: number | null;
  end_week: number | null;
  games_missed: number;
  injury: string | null;
}

export interface InjurySeason {
  season: number;
  /** The Fantasy Sim names a season "S3 2028"; the real record leaves it out and shows the year. */
  season_label?: string;
  games_missed: number;
  stints: InjuryStint[];
}

export interface CurrentInjury {
  label: string;
  status: string;
  severity: string;
  unavailable: boolean;
  body_part: string | null;
  practice: string | null;
  report: string | null;
  /** "Hamstring · Questionable" */
  line: string;
}

export interface InjuryRecordData {
  ok: boolean;
  player_id?: string;
  /** The in-progress (or latest) season the "this season" figure refers to. */
  current_season?: number;
  current: CurrentInjury | null;
  seasons: InjurySeason[];
  career_games_missed: number;
  since_season: number | null;
  source?: string;
  method?: string;
}

export function gamesLabel(n: number): string {
  return `${n} ${n === 1 ? "game" : "games"}`;
}

/** "Wk 4" or "Wk 4-5". */
export function weeksLabel(stint: InjuryStint): string {
  if (stint.start_week == null) return "";
  if (stint.end_week == null || stint.end_week === stint.start_week) return `Wk ${stint.start_week}`;
  return `Wk ${stint.start_week}–${stint.end_week}`;
}

/** The slot the chart is for, e.g. "RB2": the first letters of the slot code plus his order. */
export function depthRoleLabel(slot: string | null | undefined, order: number | null | undefined): string | null {
  if (!slot || order == null) return null;
  return `${slot}${order}`;
}

/** Collapsed summary of the depth chart: "RB2 · KC · 2 ahead". Empty when he is not on a chart. */
export function depthChartParts(chart: DepthChartData | null | undefined): CompactPart[] {
  if (!chart || !chart.ok || chart.self_order == null || chart.entries.length === 0) return [];
  const mine = chart.entries.find((e) => e.is_self);
  const ahead = chart.entries.filter((e) => e.order < chart.self_order!).length;
  const moved = mine ? depthChange(mine.change) : null;
  const parts: CompactPart[] = [
    { key: "role", text: depthRoleLabel(chart.slot, chart.self_order) ?? "", strong: true, tone: chart.self_order === 1 ? "success" : undefined },
    { key: "team", text: chart.team ?? "" },
    { key: "ahead", text: chart.self_order === 1 ? "Starter" : `${ahead} ahead`, tone: chart.self_order === 1 ? "success" : "muted" },
  ];
  if (moved) parts.push({ key: "moved", text: moved.text, tone: moved.tone });
  return parts;
}

export interface DepthChange {
  text: string;
  tone: "success" | "danger";
  arrow: "up" | "down";
}

/** "Up 1" / "Down 2" since the last weekly reading; null when unchanged or unknown. */
export function depthChange(change: number | null | undefined): DepthChange | null {
  if (change == null || change === 0) return null;
  const n = Math.abs(change);
  return change > 0 ? { text: `Up ${n}`, tone: "success", arrow: "up" } : { text: `Down ${n}`, tone: "danger", arrow: "down" };
}

/** Who is ahead / behind / him, in order, for the list. */
export function depthRowKind(entry: DepthChartEntry, selfOrder: number | null): "ahead" | "self" | "behind" {
  if (entry.is_self) return "self";
  return selfOrder != null && entry.order < selfOrder ? "ahead" : "behind";
}

/** One line of the injury section's collapsed summary: current injury (or Healthy), this season, career. */
export function injurySummaryParts(record: InjuryRecordData | null | undefined): CompactPart[] {
  if (!record || !record.ok) return [];
  const currentSeason = record.current_season ?? new Date().getFullYear();
  const thisSeason = record.seasons.find((s) => s.season === currentSeason)?.games_missed ?? 0;
  const parts: CompactPart[] = [
    record.current
      ? { key: "current", text: record.current.line, strong: true, tone: record.current.unavailable ? "danger" : "warning" }
      : { key: "current", text: "Healthy", tone: "success" },
  ];
  if (record.career_games_missed > 0) {
    parts.push({ key: "season", text: thisSeason > 0 ? `${gamesLabel(thisSeason)} missed in ${currentSeason}` : `0 missed in ${currentSeason}` });
    parts.push({ key: "career", text: `${record.career_games_missed} career` });
  } else {
    parts.push({ key: "none", text: "No games missed on record", tone: "muted" });
  }
  return parts;
}

export interface InjuryHistoryRow {
  key: string;
  season: number;
  seasonLabel: string;
  injury: string;
  weeks: string;
  games: string;
}

/** The expanded history, newest first: one row per stint. */
export function injuryHistoryRows(record: InjuryRecordData | null | undefined): InjuryHistoryRow[] {
  if (!record || !record.ok) return [];
  const rows: InjuryHistoryRow[] = [];
  for (const season of record.seasons) {
    for (const stint of [...season.stints].reverse()) {
      rows.push({
        key: `${season.season}-${stint.start_week ?? "x"}`,
        season: season.season,
        seasonLabel: season.season_label || String(season.season),
        injury: stint.injury ?? "Injury (not specified)",
        weeks: weeksLabel(stint),
        games: gamesLabel(stint.games_missed),
      });
    }
  }
  return rows;
}

/** "2021-2026" style coverage note under the history. */
export function injuryCoverageNote(record: InjuryRecordData | null | undefined): string | null {
  if (record?.ok && record.source === "sim") return "From this game's own injury log.";
  if (!record || !record.ok || record.since_season == null) return null;
  return `Career total counts ${record.since_season} onward (official NFL injury reports).`;
}
