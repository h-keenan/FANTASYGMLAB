// Shared (web + mobile twin): the adapter between a Fantasy Sim player payload and the
// real Player Quick View. The sim never renders its own bespoke player block; it feeds
// these values to the same quick view (hero tiles, weekly chart, trends) and the same
// section components, so the two can not drift apart.

import { simDraftRowChips } from "./simDraft";
import { simPlayerTags, type SimGameTone, type SimGamePlayer, type SimPlayerDetailResponse, type SimRosSummary } from "./simGame";
import { isFlatProjection, type WeeklyActualPoint, type WeeklyProjectionPoint } from "./weeklyProjection";

export interface SimHeroFeed {
  /** Value tile number, or null (the tile shows an em dash with `valueNote`). */
  score: number | null;
  valueNote: string | null;
  overall_rank: number | null;
  position_rank: number | null;
  /** Overall 1-99, the same number the list rows show; drives the hero's Player score ring. */
  overall_rating: number | null;
}

/**
 * What the hero tiles get for a sim player. A value of 0 means "no market value" in this
 * league (below replacement), never a real zero: it renders as an em dash with a reason,
 * and the player still shows the sim's own value rank so the tile row is not empty.
 */
export function simHeroFeed(player: Pick<SimGamePlayer, "value" | "value_rank" | "pos_value_rank" | "kind" | "overall">): SimHeroFeed {
  const hasValue = typeof player.value === "number" && player.value > 0;
  return {
    score: hasValue ? Math.round(player.value) : null,
    valueNote: hasValue ? null : "No market value in this league (below replacement level)",
    overall_rank: player.value_rank ?? null,
    position_rank: player.pos_value_rank ?? null,
    overall_rating: player.overall ?? null,
  };
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

/** The projection band even when it is flat (a steady line with its floor/ceiling): the Outlook chart always has something to draw. Bye and out weeks are gaps. */
export function simOutlookBand(detail: Pick<SimPlayerDetailResponse, "weeks">): WeeklyProjectionPoint[] | null {
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

// ---------------------------------------------------------------------------
// Hero tiles, outlook tiles and the profile read for players without a scouting report (2026-11-14 UI pass).

export interface SimTile {
  label: string;
  value: string;
  note: string;
  percentile: null;
}

function pts(n: number | null | undefined): string {
  return typeof n === "number" && Number.isFinite(n) ? (Math.round(n * 10) / 10).toFixed(1) : "—";
}

/**
 * The two hero tiles a sim player gets in place of the real app's Value and Usage tiles (the sim never shows the model's
 * value and has no real usage feed): what he projects for his next game and where the market (ADP) has him.
 */
export function simHeroTiles(player: Pick<SimGamePlayer, "projection" | "next_projection" | "projection_note" | "status" | "out_weeks" | "floor" | "ceiling" | "adp" | "adp_edge">): SimTile[] {
  const out = player.projection_note === "out" || player.status === "out";
  const bye = player.projection_note === "bye" || (!out && player.status === "bye");
  const week: SimTile = out
    ? { label: "This week", value: "Out", note: player.out_weeks > 0 ? `${player.out_weeks} ${player.out_weeks === 1 ? "week" : "weeks"}` : "Not playing", percentile: null }
    : bye
      ? { label: "This week", value: "Bye", note: player.next_projection != null ? `Next ${pts(player.next_projection)}` : "Not playing", percentile: null }
      : { label: "This week", value: pts(player.projection), note: `${pts(player.floor)}-${pts(player.ceiling)} range`, percentile: null };
  const edge = player.adp_edge ?? 0;
  const adp: SimTile = {
    label: "ADP",
    value: player.adp != null ? String(Math.round(player.adp)) : "—",
    note: player.adp == null ? "No ADP" : edge > 0 ? `Falls ${edge} past the sim` : edge < 0 ? `Goes ${Math.abs(edge)} early` : "Right on the market",
    percentile: null,
  };
  return [week, adp];
}

/** Rest-of-season tiles for the Outlook tab: per game, range, games left and availability. */
export function simOutlookTiles(ros: SimRosSummary | null | undefined): SimTile[] {
  if (!ros) return [];
  const availability = simAvailabilityLine(ros);
  return [
    { label: "Per game", value: pts(ros.mean), note: "rest of season", percentile: null },
    { label: "Range", value: `${pts(ros.floor)}-${pts(ros.ceiling)}`, note: ros.mean > 0 && ros.ceiling - ros.floor > ros.mean * 1.6 ? "boom or bust" : "steady", percentile: null },
    { label: "Games left", value: String(ros.playable_weeks ?? ros.weeks_left ?? 0), note: ros.weeks_left > (ros.playable_weeks ?? 0) ? `of ${ros.weeks_left} weeks` : "healthy weeks", percentile: null },
    { label: "Availability", value: availability ? (ros.out_weeks?.length ? "Misses time" : "Bye ahead") : "Clear", note: availability ?? "No bye or injury ahead", percentile: null },
  ];
}

export type SimAgePhase = "rising" | "prime" | "declining" | "late";

/** Typical windows by position: last age of each phase. Football convention, not a model output. */
const AGE_WINDOWS: Record<string, [number, number, number]> = {
  QB: [25, 34, 37],
  RB: [23, 27, 29],
  WR: [24, 29, 32],
  TE: [25, 30, 33],
  K: [26, 38, 41],
};

export function simAgePhase(pos: string, age: number | null | undefined): { phase: SimAgePhase; label: string; tone: SimGameTone; line: string } | null {
  if (age == null) return null;
  const w = AGE_WINDOWS[pos] ?? AGE_WINDOWS.WR;
  if (age <= w[0]) return { phase: "rising", label: "Rising", tone: "accent", line: `Age ${age}: still climbing for a ${pos}.` };
  if (age <= w[1]) return { phase: "prime", label: "Prime", tone: "success", line: `Age ${age}: inside the usual ${pos} prime.` };
  if (age <= w[2]) return { phase: "declining", label: "Declining", tone: "warning", line: `Age ${age}: past the usual ${pos} prime; production tends to slip.` };
  return { phase: "late", label: "Late career", tone: "danger", line: `Age ${age}: late for a ${pos}; retirement is a real risk.` };
}

export interface SimProfileRead {
  /** Heading badge, e.g. "Prime". */
  phase: { label: string; tone: SimGameTone } | null;
  chips: { key: string; label: string }[];
  tiles: SimTile[];
  /** Plain sentences, one per line: age, steadiness, market. */
  lines: string[];
}

/**
 * The Scouting tab for a player who has no generated scouting report (every veteran): a profile read built only from fields
 * the game already sends (age window, per-game range, ADP gap, production). No model value is used or shown.
 */
export function simProfileRead(player: Pick<SimGamePlayer, "pos" | "age" | "overall" | "adp" | "adp_edge" | "projection" | "ros_mean" | "floor" | "ceiling" | "games" | "ppg" | "season_points" | "last_week" | "team">): SimProfileRead {
  const age = simAgePhase(player.pos, player.age);
  const base = player.ros_mean ?? player.projection;
  const spread = base > 0 ? (player.ceiling - player.floor) / base : 0;
  const steady = spread > 1.6 ? { label: "Boom or bust", line: "A wide week-to-week range: he wins or loses weeks on his own." } : spread < 1 ? { label: "Steady", line: "A tight range: you know roughly what you get each week." } : { label: "Balanced", line: "A normal range between his floor and ceiling." };
  const edge = player.adp_edge ?? 0;
  const market = player.adp == null ? null : edge >= 3 ? `The market lets him fall ${edge} spots past where the sim has him.` : edge <= -3 ? `The market takes him ${Math.abs(edge)} spots earlier than the sim does.` : "The market and the sim agree on where he goes.";
  const chips = [{ key: "steady", label: steady.label }, ...(player.team ? [{ key: "team", label: player.team }] : [])];
  const tiles: SimTile[] = [
    { label: "Age", value: player.age != null ? String(player.age) : "—", note: age ? age.label : "Unknown", percentile: null },
    { label: "Overall", value: player.overall != null ? String(player.overall) : "—", note: `${player.pos} rating`, percentile: null },
    { label: "Range", value: `${pts(player.floor)}-${pts(player.ceiling)}`, note: steady.label.toLowerCase(), percentile: null },
    { label: "ADP", value: player.adp != null ? String(Math.round(player.adp)) : "—", note: player.adp == null ? "No ADP" : edge > 0 ? `+${edge} vs sim` : edge < 0 ? `${edge} vs sim` : "In line", percentile: null },
  ];
  const lines = [age?.line, steady.line, market, (player.games ?? 0) > 0 ? `${pts(player.season_points ?? 0)} points in ${player.games} ${player.games === 1 ? "game" : "games"}${player.ppg != null ? ` (${pts(player.ppg)} ppg)` : ""}.` : null].filter((l): l is string => Boolean(l));
  return { phase: age ? { label: age.label, tone: age.tone } : null, chips, tiles, lines };
}
