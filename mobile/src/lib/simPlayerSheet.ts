// Shared (web + mobile twin): the adapter between a Fantasy Sim player payload and the
// real Player Quick View. The sim never renders its own bespoke player block; it feeds
// these values to the same quick view (hero tiles, weekly chart, trends) and the same
// section components, so the two can not drift apart.

import { simDraftRowChips } from "./simDraft";
import { simPlayerTags, type SimGameTone, type SimGamePlayer, type SimPlayerDetailResponse, type SimRosSummary } from "./simGame";
import { simGradeOf, type SimGradeInput } from "./simGrade";
import { isFlatProjection, type WeeklyActualPoint, type WeeklyProjectionPoint } from "./weeklyProjection";

/**
 * What the hero shows for a sim player: ONE letter grade (never the numeric Player score ring, the Value tile or an
 * overall / position rank: those would hand out the model's hidden rating). Null when there is no grade.
 */
export function simHeroGrade(player: SimGradeInput): SimGradeInput | null {
  return simGradeOf(player);
}

/** Did the server (or, for an older server, the weeks themselves) say the projection never changes week to week? */
export function simProjectionIsFlat(detail: Pick<SimPlayerDetailResponse, "weeks" | "projection_flat">): boolean {
  if (typeof detail.projection_flat === "boolean") return detail.projection_flat;
  const playable = (detail.weeks ?? []).filter((w) => !w.bye && !w.out).map((w) => ({ mean: w.projection, floor: w.floor, ceiling: w.ceiling }));
  return isFlatProjection(playable);
}

/** "Rest of season: 2.2 ppg (0.6-3.8)". */
export function simRosLine(ros: Pick<SimRosSummary, "mean" | "floor" | "ceiling">): string {
  return `Rest of season: ${ros.mean.toFixed(1)} ppg (${ros.floor.toFixed(1)}-${ros.ceiling.toFixed(1)})`;
}

/** "Bye week 7 · Out weeks 3-4" or null when nothing is notable. */
export function simAvailabilityLine(ros: Pick<SimRosSummary, "bye_week" | "out_weeks">): string | null {
  const bits: string[] = [];
  if (ros.bye_week) bits.push(`Bye week ${ros.bye_week}`);
  const out = ros.out_weeks ?? [];
  if (out.length > 0) bits.push(out.length === 1 ? `Out week ${out[0]}` : `Out weeks ${out[0]}-${out[out.length - 1]}`);
  return bits.length > 0 ? bits.join(" · ") : null;
}

/** Actual points so far this sim season, for the shared weekly chart. */
export function simActualPoints(detail: Pick<SimPlayerDetailResponse, "history">): WeeklyActualPoint[] {
  return (detail.history ?? []).map((h) => ({ week: h.week, points: h.points }));
}

/**
 * The rest-of-season band for the chart, only when it truly varies by week; a flat projection
 * returns null and the sheet shows the one-line summary instead. Bye and out weeks are left out
 * of the band (gaps), not drawn as zeros.
 */
export function simProjectionBand(detail: Pick<SimPlayerDetailResponse, "weeks" | "projection_flat">): WeeklyProjectionPoint[] | null {
  if (simProjectionIsFlat(detail)) return null;
  const pts = (detail.weeks ?? []).filter((w) => !w.bye && !w.out).map((w) => ({ week: w.week, mean: w.projection, floor: w.floor, ceiling: w.ceiling }));
  return pts.length > 0 ? pts : null;
}

export interface SimHeaderTag {
  key: string;
  label: string;
  tone: SimGameTone;
}

/**
 * The tags the Player Quick View header shows for a sim player: exactly the ones his list row shows (the single injury chip,
 * then block / owner (Free agent, Your team, an AI team) / role), so opening a tag you could not read on the list tells you what it
 * was (coridian_, 2026-11-14: "the tag is not there whatsoever, and it should also have the Free agent tag"). One owner for the
 * injury: the header does not add a second "Health: Out" chip next to it.
 */
export function simHeaderTags(player: SimGamePlayer): SimHeaderTag[] {
  const injury = simDraftRowChips(player).map((c) => ({ key: c.key, label: c.label, tone: c.tone }));
  return [...injury, ...(simPlayerTags(player) ?? [])];
}
