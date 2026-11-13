// Shared (web + mobile twin): presentation helpers for the generated-prospect scouting sections of the
// Fantasy Sim player sheet. Tiles use the same {label, value, note, percentile} shape as the real quick
// view's stat tiles, and the development curve feeds the same chart as the weekly points.

import type { SimDevelopmentCurve, SimScoutingCollege, SimScoutingProfile } from "./simGame";
import type { WeeklyProjectionPoint } from "./weeklyProjection";

export interface SimStatTile {
  label: string;
  value: string;
  note: string;
  percentile: number | null;
}

export function simFmtScoutStat(value: number, fmt: string): string {
  if (fmt === "int") return Math.round(value).toLocaleString("en-US");
  if (fmt === "num2") return value.toFixed(2);
  if (fmt === "pct1") return `${value.toFixed(1)}%`;
  return value.toFixed(1);
}

export function simDraftLine(draft: SimScoutingProfile["draft"]): string {
  return `Round ${draft.round} · Pick ${draft.pick}`;
}

/** Final-season college line as stat tiles with the percentile vs the position class. */
export function simCollegeTiles(college: SimScoutingCollege): SimStatTile[] {
  return college.columns
    .filter((c) => college.final.stats[c.key] != null)
    .map((c) => ({ label: c.label, value: simFmtScoutStat(college.final.stats[c.key], c.fmt), note: "", percentile: college.percentiles[c.key] ?? null }));
}

export function simCollegeCaption(college: SimScoutingCollege): string {
  const n = college.seasons.length;
  return `${college.final.season} · ${college.final.team} · ${college.final.games} games · ${n} college season${n === 1 ? "" : "s"}`;
}

export function simMeasurableTiles(profile: Pick<SimScoutingProfile, "measurables">): SimStatTile[] {
  return profile.measurables.map((m) => ({ label: m.label, value: m.display, note: "", percentile: m.percentile }));
}

/** The development curve as a band for the shared chart (the chart's "week" axis carries the year). */
export function simCurveBand(dev: Pick<SimDevelopmentCurve, "points">): WeeklyProjectionPoint[] {
  return dev.points.map((p) => ({ week: p.year, mean: p.mean, floor: p.lo, ceiling: p.hi }));
}

export function simCurveCaption(dev: Pick<SimDevelopmentCurve, "points">): string {
  if (dev.points.length === 0) return "";
  const first = dev.points[0];
  const last = dev.points[dev.points.length - 1];
  if (first.year === last.year) return `Year ${first.year}: ${first.mean.toFixed(1)} ppg`;
  return `Year ${first.year} ${first.mean.toFixed(1)} → Year ${last.year} ${last.mean.toFixed(1)} ppg`;
}

/** "Medium confidence" style label for a tag. */
export function simTagConfidenceLabel(confidence: number): "Low" | "Medium" | "High" {
  return confidence >= 0.7 ? "High" : confidence >= 0.4 ? "Medium" : "Low";
}

export function simPercentileBand(percentile: number): "low" | "mid" | "high" {
  return percentile >= 70 ? "high" : percentile >= 35 ? "mid" : "low";
}

/** 1 -> "1st", 22 -> "22nd", 93 -> "93rd", 11 -> "11th". */
export function simOrdinal(n: number): string {
  const v = Math.round(n);
  const mod100 = v % 100;
  if (mod100 >= 11 && mod100 <= 13) return `${v}th`;
  return `${v}${{ 1: "st", 2: "nd", 3: "rd" }[v % 10] ?? "th"}`;
}
