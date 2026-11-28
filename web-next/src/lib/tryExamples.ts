/**
 * This week's real-player examples for /try/start-sit and /try/waivers, from GET /v1/public/try-examples
 * (modules/public_try_examples.py: verified matchup points-allowed, projections, Sleeper trending adds and roster %).
 * Anything missing or malformed returns null for that section and the page falls back to the labelled sample league
 * (lib/sampleTryData.ts). Never fabricates.
 */

import { apiBases } from "@/lib/seo/publicValues";
import { bid, priorityAdd, waiverPlayer } from "@/lib/sampleTryData";
import type { MatchupResponse, MatchupSuggestedMove, WaiversResponse } from "@/lib/api";

export const REAL_EXAMPLE_LABEL = "Example decision using this week's real players, not your league";

export interface RealStartSit {
  move: MatchupSuggestedMove;
  matchup_note: string;
}

export interface RealWaiverAdd {
  player_id: string;
  name: string;
  position: string;
  team: string | null;
  age: number | null;
  score: number | null;
  position_rank: number;
  overall_rank: number | null;
  overall_rating: number | null;
  tier: string;
  trending_adds_24h: number;
  trending_rank: number;
  roster_pct: number;
  injury_cover_for: string | null;
  reason: string;
  bid: { low: number; high: number; budget: number };
}

export interface TryExamples {
  season: number | null;
  week: number | null;
  startSit: RealStartSit | null;
  waivers: RealWaiverAdd[] | null;
}

const isObj = (v: unknown): v is Record<string, unknown> => !!v && typeof v === "object";
const isNum = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);
const isStr = (v: unknown): v is string => typeof v === "string" && v.trim() !== "";

function isMovePlayer(v: unknown): boolean {
  return isObj(v) && isStr(v.player_id) && isStr(v.name) && isStr(v.position) && isNum(v.points);
}

function parseStartSit(v: unknown): RealStartSit | null {
  if (!isObj(v) || !isObj(v.move) || !isStr(v.matchup_note)) return null;
  const m = v.move;
  if (!isMovePlayer(m.start) || !isMovePlayer(m.over) || !isNum(m.gain)) return null;
  return { move: m as unknown as MatchupSuggestedMove, matchup_note: v.matchup_note };
}

function parseAdd(v: unknown): RealWaiverAdd | null {
  if (!isObj(v) || !isStr(v.player_id) || !isStr(v.name) || !isStr(v.position) || !isStr(v.reason)) return null;
  const b = v.bid;
  if (!isObj(b) || !isNum(b.low) || !isNum(b.high) || !isNum(b.budget) || !isNum(v.position_rank) || !isNum(v.roster_pct)) return null;
  if (!isNum(v.trending_adds_24h) || !isNum(v.trending_rank)) return null;
  return v as unknown as RealWaiverAdd;
}

export function parseTryExamples(value: unknown): TryExamples | null {
  if (!isObj(value) || value.ok !== true) return null;
  const adds = Array.isArray((value.waivers as { adds?: unknown } | null)?.adds)
    ? ((value.waivers as { adds: unknown[] }).adds.map(parseAdd).filter((a): a is RealWaiverAdd => a !== null))
    : [];
  return {
    season: isNum(value.season) ? value.season : null,
    week: isNum(value.week) ? value.week : null,
    startSit: parseStartSit(value.start_sit),
    waivers: adds.length > 0 ? adds : null,
  };
}

/** Null on any transport failure, so the pages render their labelled sample-league fallback. */
export async function fetchTryExamples(): Promise<TryExamples | null> {
  for (const base of apiBases()) {
    try {
      const response = await fetch(`${base}/v1/public/try-examples`, { next: { revalidate: 3600 }, signal: AbortSignal.timeout(6000) });
      if (!response.ok) continue;
      const parsed = parseTryExamples(await response.json());
      if (parsed) return parsed;
    } catch {
      // try the next base
    }
  }
  return null;
}

/** A matchup payload carrying only what the Suggested Moves module reads. */
export function realStartSitMatchup(ex: RealStartSit): MatchupResponse {
  return {
    ok: true,
    week: null,
    my_team: null,
    opponent: null,
    comparison: null,
    real_comparison: null,
    win_probability: null,
    suggested_moves: [ex.move],
    basis: "season_value",
    basis_label: "Projected points",
    reason: "",
  };
}

export function realWaiversResponse(adds: RealWaiverAdd[]): WaiversResponse {
  const players = adds.map((a) =>
    waiverPlayer({
      player_id: a.player_id,
      name: a.name,
      position: a.position,
      team: a.team,
      age: a.age,
      tier: a.tier,
      opportunity_label: a.tier === "starter" ? "Starter Range" : "Backup With Upside",
      score: a.score,
      position_rank: a.position_rank,
      overall_rank: a.overall_rank,
      injury_replacement_fit: !!a.injury_cover_for,
      sleeper_trending_add: true,
      sleeper_trending_add_count: a.trending_adds_24h,
      sleeper_trending_add_rank: a.trending_rank,
      overall_rating: a.overall_rating,
    }),
  );
  return {
    ok: true,
    reason: "",
    players,
    priority_adds: adds.map((a, i) =>
      priorityAdd(players[i], {
        recommendation_label: "Add",
        recommendation_tone: "opportunity",
        confidence_label: "Medium",
        confidence_reason: "Built from Sleeper's league-wide add and roster data, not your roster.",
        recommendation_reason: a.reason,
        injury_cover_for: a.injury_cover_for ?? undefined,
        faab: bid(a.bid.low, a.bid.high),
      }),
    ),
    needed_positions: [],
    available_count: adds.length,
    avg_wire_score: 0,
    injured_starters: 0,
    injury_positions: [],
    faab_remaining: adds[0]?.bid.budget ?? 100,
    faab_initial: adds[0]?.bid.budget ?? 100,
    faab_enabled: true,
    stash_candidates: [],
    watchlist_candidates: [],
    faab_targets: [],
    entitlement: { is_premium: true },
  };
}
