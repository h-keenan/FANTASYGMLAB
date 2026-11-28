/**
 * Commissioner "Lineup check" presentation, shared by web and the app. This file is byte-identical to
 * mobile/src/lib/commissionerLineups.ts (a mobile test compares them): edit both together. Pure TS, no imports.
 * Engine: modules/commissioner_lineups.py, endpoint GET /v1/leagues/{id}/commissioner/lineups.
 */

export type LineupFlagKind = "no_lineup" | "out" | "ir" | "bye" | "empty";

export interface LineupFlag {
  kind: LineupFlagKind;
  label: string;
  player: string | null;
  slot: string | null;
}

/** A locked, hurt starter (got hurt after kickoff): nothing to fix, so it is information, never a flag. */
export interface LineupInfo {
  kind: string;
  label: string;
  player: string | null;
  slot: string | null;
}

export interface LineupStarter {
  slot: string | null;
  player_id: string | null;
  name: string | null;
  position: string | null;
  team: string | null;
  points: number | null;
  availability: "bye" | "ir" | "out" | null;
  injury_label: string;
  locked: boolean;
}

export interface LineupSwapSide {
  player_id: string | null;
  name: string | null;
  position: string | null;
  team: string | null;
  points: number | null;
}

export interface LineupSwap {
  slot: string | null;
  start: LineupSwapSide | null;
  over: LineupSwapSide | null;
  over_reason: string | null;
  gain: number | null;
}

export interface LineupCheckTeam {
  roster_id: string;
  team_name: string;
  owner_name: string | null;
  avatar_url: string | null;
  has_lineup: boolean;
  starters: LineupStarter[];
  set_points: number | null;
  best_points: number | null;
  gap: number | null;
  gap_pct: number | null;
  partial: boolean;
  possible_tanking: boolean;
  flags: LineupFlag[];
  info?: LineupInfo[];
  locked_count: number;
  swaps: LineupSwap[];
}

export interface CommissionerLineupsResponse {
  ok: boolean;
  is_premium: boolean;
  upsell?: { title?: string; body?: string } | null;
  reason: string;
  week: number | null;
  projection_ready: boolean;
  teams: LineupCheckTeam[];
  limits?: string[];
}

export function normalizeCommissionerLineups(raw: unknown): CommissionerLineupsResponse {
  const r = (raw && typeof raw === "object" ? raw : {}) as Record<string, unknown>;
  const teams = Array.isArray(r.teams) ? (r.teams as Record<string, unknown>[]) : [];
  return {
    ...r,
    ok: r.ok === true,
    is_premium: r.is_premium !== false,
    reason: typeof r.reason === "string" ? r.reason : "",
    week: typeof r.week === "number" ? r.week : null,
    projection_ready: r.projection_ready === true,
    teams: teams.map((t) => ({
      ...t,
      starters: Array.isArray(t.starters) ? t.starters : [],
      flags: Array.isArray(t.flags) ? t.flags : [],
      info: Array.isArray(t.info) ? t.info : [],
      swaps: Array.isArray(t.swaps) ? t.swaps : [],
      locked_count: typeof t.locked_count === "number" ? t.locked_count : 0,
    })) as unknown as LineupCheckTeam[],
    limits: Array.isArray(r.limits) ? (r.limits as string[]) : [],
  } as CommissionerLineupsResponse;
}

export function lineupsReasonMessage(reason: string): string {
  switch (reason) {
    case "no_current_week":
      return "There is no live week yet. This check opens once the season starts.";
    case "no_matchup_data":
      return "Sleeper has not posted this week's matchups yet.";
    case "best_ball":
      return "Best-ball leagues set lineups automatically, so there is nothing to check.";
    case "unsupported_platform":
      return "The lineup check reads Sleeper leagues. Imported leagues are not supported yet.";
    case "no_player_data":
      return "Player data is still loading. Try again in a minute.";
    default:
      return "Nothing to show yet.";
  }
}

export function formatPoints(n: number | null | undefined): string {
  return typeof n === "number" ? n.toFixed(1) : "n/a";
}

/** Gap is always shown as points left on the bench: "-14.2" (never a red verdict, the tone stays warning/muted). */
export function gapLabel(team: Pick<LineupCheckTeam, "gap">): string {
  if (team.gap == null) return "n/a";
  return team.gap <= 0 ? "Even" : `-${team.gap.toFixed(1)}`;
}

export type LineupTone = "warning" | "success" | "muted" | "information";

export function gapTone(team: Pick<LineupCheckTeam, "gap" | "possible_tanking">): LineupTone {
  if (team.gap == null) return "muted";
  if (team.possible_tanking) return "warning";
  return team.gap <= 0.05 ? "success" : "muted";
}

export function flagTone(kind: LineupFlagKind): LineupTone {
  return kind === "bye" ? "information" : "warning";
}

/** Chip text for a flag, with the player when there is one: "Out: J. Smith". */
export function flagText(flag: LineupFlag): string {
  if (flag.kind === "empty") return flag.slot ? `Empty ${flag.slot}` : flag.label;
  return flag.player ? `${flag.label}: ${flag.player}` : flag.label;
}

/** Chip text for an info note, with the player: "Left game (injury): J. Smith". */
export function infoText(note: LineupInfo): string {
  return note.player ? `${note.label}: ${note.player}` : note.label;
}

/** One-line numbers under a team name: "Set 98.2 · Best 112.4". */
export function setVsBestLine(team: Pick<LineupCheckTeam, "set_points" | "best_points">): string {
  if (team.set_points == null || team.best_points == null) return "No projections yet";
  return `Set ${formatPoints(team.set_points)} · Best ${formatPoints(team.best_points)}`;
}

export function swapLine(swap: LineupSwap): string {
  const start = swap.start?.name ?? "Bench player";
  const over = swap.over?.name ?? (swap.over_reason === "empty_slot" ? "an empty slot" : "the current starter");
  const gain = typeof swap.gain === "number" ? ` (+${swap.gain.toFixed(1)})` : "";
  return `${swap.slot ? `${swap.slot}: ` : ""}Start ${start} over ${over}${gain}`;
}

export function lineupsSummaryLine(resp: Pick<CommissionerLineupsResponse, "teams" | "week" | "projection_ready">): string {
  const wk = resp.week ? `Week ${resp.week}` : "This week";
  if (!resp.projection_ready) return `${wk}: no projections yet, so only lineup problems (injured, bye, empty slots) are shown.`;
  const tanking = resp.teams.filter((t) => t.possible_tanking).length;
  const flagged = resp.teams.filter((t) => t.flags.length > 0).length;
  if (!tanking && !flagged) return `${wk}: every team's lineup is close to its best.`;
  const parts: string[] = [];
  if (tanking) parts.push(`${tanking} team${tanking === 1 ? "" : "s"} with a big gap`);
  if (flagged) parts.push(`${flagged} with lineup problems`);
  return `${wk}: ${parts.join(", ")}.`;
}
