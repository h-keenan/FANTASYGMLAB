/**
 * Fantasy Sim: the GM Game. Shared types and pure presentation helpers for the
 * interactive, turn-based game (docs/fantasy-sim-api.md, "GM game" half;
 * design in docs/fantasy-sim-game-design.md). Web and mobile hold a
 * byte-identical copy of this file (scripts/check_lib_twins.mjs), so it has no
 * imports and no platform code: every screen renders from these shapes and
 * formatters and never restates a rule the backend already decided.
 *
 * Not to be confused with lib/simPresentation.ts, the Season Outlook
 * forecast (a one-tap read on a real league). The game is standalone: nothing here
 * reads or writes real league data.
 */

import type { ReviewGlyph } from "./simReview";

// ---------------------------------------------------------------------------
// Envelope, gating and reasons

export type SimGameStatus = "drafting" | "in_season" | "playoffs" | "complete";
export type SimGamePhase = "draft" | "regular_season" | "playoffs" | "complete";
export type SimScoring = "ppr" | "half" | "std";
export type SimDifficulty = "easy" | "normal" | "hard";
export type SimTiebreaker = "points_for" | "head_to_head";
export const SIM_TIEBREAKER_LABELS: Record<SimTiebreaker, string> = { points_for: "Points for", head_to_head: "Head-to-head" };
export type SimPos = "QB" | "RB" | "WR" | "TE" | "K" | "DEF";
export type SimSlot = "QB" | "RB" | "WR" | "TE" | "FLEX" | "REC_FLEX" | "SUPER_FLEX" | "K" | "DEF";
/** League mode. Only redraft is playable today; dynasty is declared by the API (available: false). */
export type SimMode = "redraft" | "dynasty";
/** How a new game starts: a fresh draft, or a real league's rosters (read-only import). */
export type SimStartKind = "fresh" | "league";

export interface SimGameUpsell {
  title: string;
  body: string;
}

/** `preview` is null for Pro; for Free it counts down the paid-for-free weeks. */
export interface SimGamePreview {
  weeks_left: number;
  paywall_week: number;
  paywalled: boolean;
}

/** Fields every /v1/sim/games* body carries (success or not-ready). */
export interface SimGameEnvelope {
  ok?: boolean;
  reason?: string;
  error?: string;
  /** Plain sentence the engine wrote for a rule `reason` (not-ready states). */
  message?: string;
  is_premium?: boolean;
  upsell?: SimGameUpsell | null;
  preview?: SimGamePreview | null;
  /** On `game_limit_reached`. */
  max_games?: number;
  /** On `wrong_phase`. */
  phase?: string;
  /** On `roster_over_limit`. */
  cuts_needed?: number;
}

export interface SimPlayerOwner {
  type: "you" | "ai" | "free_agent";
  team_id?: string | null;
  name?: string | null;
}

export interface SimGamePlayer {
  id: string;
  /** Sleeper player id to fetch a photo with; null for defenses and synthetic players. */
  headshot_id?: string | null;
  name: string;
  pos: SimPos;
  /** NFL team. */
  team: string | null;
  age: number | null;
  adp: number | null;
  value: number;
  projection: number;
  floor: number;
  ceiling: number;
  status: "healthy" | "out" | "bye";
  out_weeks: number;
  bye_week: number | null;
  owner?: SimPlayerOwner | null;
  last_week?: number | null;
  season_points?: number | null;
  games?: number;
  ppg?: number | null;
}

export interface SimGameTeamLine {
  team_id: string;
  name: string;
  wins: number;
  losses: number;
  ties: number;
  pf: number;
  pa: number;
  rank: number | null;
  seed: number | null;
}

export interface SimGameSettings {
  teams: number;
  scoring: SimScoring;
  difficulty: SimDifficulty;
  regular_weeks: number;
  playoff_teams: number;
  playoff_weeks: number;
  trade_deadline_week: number;
  roster_limit: number;
  rounds: number;
  slots: SimSlot[];
  user_slot: number;
  auto_lineup: boolean;
  /** League shape (older saves omit these; use simSettingsView). */
  mode?: SimMode;
  te_premium?: number;
  superflex?: boolean;
  include_k?: boolean;
  include_def?: boolean;
  bench?: number;
  start?: SimStartKind;
  /** Standings/seed tiebreak after record (older saves omit it and used head_to_head). */
  tiebreaker?: SimTiebreaker;
}

export interface SimGameThisWeek {
  week: number;
  opponent: { team_id: string; name: string; persona_id: string } | null;
  bye: boolean;
  your_projection: number;
  opponent_projection: number;
}

export interface SimGamePending {
  claims: number;
  inbox: number;
  lineup_warnings: number;
  roster_size: number;
  roster_limit: number;
  cuts_needed: number;
}

export interface SimGame {
  id: string;
  status: SimGameStatus;
  /** Week to be played next (0 while drafting). */
  week: number;
  phase: SimGamePhase;
  round: number | null;
  seed: number;
  engine_version: string;
  scoring_model?: string;
  settings: SimGameSettings;
  you: SimGameTeamLine | null;
  this_week: SimGameThisWeek | null;
  pending: SimGamePending | null;
  can_trade: boolean;
  trade_deadline_week: number;
  grade_letter: string | null;
  created_at: string;
  updated_at: string;
}

/** The cheap list row from GET /v1/sim/games. */
export interface SimGameLite {
  id: string;
  seed: number;
  engine_version: string;
  settings: Partial<SimGameSettings>;
  status: SimGameStatus;
  current_week: number;
  difficulty: SimDifficulty;
  grade_letter: string | null;
  event_count: number;
  created_at: string;
  updated_at: string;
}

export interface SimGamePersona {
  id: string;
  label: string;
  blurb: string;
}

export interface SimGameOptionsResponse extends SimGameEnvelope {
  engine_version?: string;
  max_games?: number;
  options?: {
    mode?: { values: SimMode[]; default: SimMode; modes?: { id: SimMode; label: string; available: boolean }[] };
    teams: { values: number[]; default: number };
    scoring: { values: SimScoring[]; default: SimScoring };
    te_premium?: { values: number[]; default: number };
    superflex?: { default: boolean };
    include_k?: { default: boolean };
    include_def?: { default: boolean };
    bench?: { min: number; max: number; default: number };
    difficulty: { values: SimDifficulty[]; default: SimDifficulty };
    user_slot: { min: number; max: number; default: number | null };
    auto_lineup: { default: boolean };
    /** Preset fantasy-style team names for a fresh league. */
    team_names?: { values: string[]; max_length: number };
    tiebreaker?: { values: SimTiebreaker[]; default: SimTiebreaker };
  };
  /** Lineup rule the setup form mirrors to show roster size and draft rounds. */
  layout?: { base_slots: SimSlot[]; draft_spare_spots: number };
  start_modes?: { id: string; available: boolean; reason?: string }[];
  season?: {
    regular_weeks: number;
    playoff_weeks: number;
    playoff_teams: number;
    trade_deadline_week: number;
    roster_limit: number;
    draft_rounds: number;
    slots: SimSlot[];
  };
  personas?: SimGamePersona[];
}

/** One team of a real league, for the "which team is yours" picker. Always sent back by `roster_id`. */
export interface SimImportTeam {
  roster_id: string;
  team_name: string;
  owner_name: string;
  wins: number;
  losses: number;
  ties: number;
  points_for: number;
  rank: number;
  is_you: boolean;
}

export interface SimLeagueTeamsResponse extends SimGameEnvelope {
  league_id?: string;
  league_name?: string;
  season?: string;
  /** The account's own roster, or null when it could not be identified. */
  you_roster_id?: string | null;
  teams?: SimImportTeam[];
}

export interface SimGameCreateBody {
  teams?: number;
  scoring?: SimScoring;
  te_premium?: number;
  superflex?: boolean;
  include_k?: boolean;
  include_def?: boolean;
  bench?: number;
  tiebreaker?: SimTiebreaker;
  mode?: SimMode;
  difficulty?: SimDifficulty;
  user_slot?: number | null;
  auto_lineup?: boolean;
  team_name?: string;
  /** Fresh league: let the server pick a preset name. */
  random_team_name?: boolean;
  /** "league": start from a real league's rosters (read-only). */
  start?: SimStartKind;
  league_id?: string;
  roster_id?: string;
}

// ---------------------------------------------------------------------------
// Draft

export interface SimDraftTeam {
  team_id: string;
  name: string;
  persona_id?: string;
  is_you: boolean;
}

export interface SimDraftPick {
  pick_no: number;
  round: number;
  team_id: string;
  player: SimGamePlayer;
  adp: number | null;
  value_over_adp: number | null;
  auto: boolean;
}

export interface SimDraftState {
  status: "in_progress" | "complete";
  pick_no: number;
  round: number;
  total_picks: number;
  on_the_clock: { team_id: string; name: string; is_you: boolean } | null;
  your_pick_numbers: number[];
  picks_until_you: number;
  order?: { pick_no: number; round: number; team_id: string }[];
  picks?: SimDraftPick[];
  queue: string[];
  your_roster: SimGamePlayer[];
  teams?: SimDraftTeam[];
}

export interface SimDraftAvailable {
  items: SimGamePlayer[];
  total: number;
  page: number;
  page_size: number;
}

export interface SimDraftHint {
  player: SimGamePlayer;
  why: string;
}

export interface SimDraftResponse extends SimGameEnvelope {
  draft?: SimDraftState;
  available?: SimDraftAvailable;
  hint?: SimDraftHint | null;
  game?: SimGame;
}

export interface SimDraftRecapTeam {
  team_id: string;
  name: string;
  grade: string;
  starter_projection: number;
  best_pick?: SimDraftPick | { player: SimGamePlayer } | null;
  worst_pick?: SimDraftPick | { player: SimGamePlayer } | null;
  is_you?: boolean;
}

export interface SimDraftRecap {
  picks_value?: unknown[];
  teams: SimDraftRecapTeam[];
  your_team?: SimDraftRecapTeam | null;
}

export interface SimDraftPickResponse extends SimGameEnvelope {
  picks?: SimDraftPick[];
  draft?: SimDraftState;
  completed?: boolean;
  recap?: SimDraftRecap | null;
  game?: SimGame;
}

// ---------------------------------------------------------------------------
// Players, lineup, waivers

export interface SimGamePlayersResponse extends SimGameEnvelope {
  items?: SimGamePlayer[];
  total?: number;
  page?: number;
  page_size?: number;
}

export interface SimPlayerWeek {
  week: number;
  projection: number;
  floor: number;
  ceiling: number;
  bye: boolean;
  out: boolean;
}

export interface SimPlayerDetailResponse extends SimGameEnvelope {
  player?: SimGamePlayer;
  weeks?: SimPlayerWeek[];
  history?: { week: number; points: number; stats?: Record<string, number> | null }[];
  news?: { week: number; text: string }[];
}

export interface SimLineupSlot {
  slot: SimSlot;
  player: SimGamePlayer | null;
}

export interface SimLineupWarning {
  code: "bye" | "out" | "empty_slot";
  slot: SimSlot;
  player_id?: string;
}

export interface SimLineupResponse extends SimGameEnvelope {
  week?: number;
  slots?: SimLineupSlot[];
  bench?: SimGamePlayer[];
  projected_total?: number;
  warnings?: SimLineupWarning[];
  roster_size?: number;
  roster_limit?: number;
  opponent?: { team_id: string; name: string } | null;
  locked?: boolean;
}

export interface SimWaiverClaim {
  id: string;
  add: SimGamePlayer;
  drop: SimGamePlayer | null;
  start_slot: SimSlot | null;
}

export interface SimWaiverResponse extends SimGameEnvelope {
  claim_id?: string;
  claim?: SimWaiverClaim;
  claims?: SimWaiverClaim[];
}

export interface SimCutResponse extends SimGameEnvelope {
  roster?: SimGamePlayer[];
}

export interface SimTeamRosterResponse extends SimGameEnvelope {
  team_id?: string;
  players?: SimGamePlayer[];
}

// ---------------------------------------------------------------------------
// Trades and inbox

export type SimTradeDecision = "accept" | "counter" | "decline";

export interface SimTradeVerdict {
  decision: SimTradeDecision;
  reason_code?: string;
  reason: string;
  chips?: string[];
  counter?: { give: SimGamePlayer[]; get: SimGamePlayer[] } | null;
}

export interface SimTradeResponse extends SimGameEnvelope {
  verdict?: SimTradeVerdict;
  executed?: boolean;
  trade?: unknown;
  roster?: SimGamePlayer[];
  pending?: SimGamePending;
}

export interface SimInboxItem {
  id: string;
  type: "trade_offer";
  from: { team_id: string; name: string; persona_id?: string };
  you_give: SimGamePlayer[];
  you_get: SimGamePlayer[];
  message: string;
  expires_week: number;
}

export interface SimInboxResponse extends SimGameEnvelope {
  items?: SimInboxItem[];
  executed?: boolean;
}

// ---------------------------------------------------------------------------
// Advance, recap, league, result

export type SimGameResultKind = "win" | "loss" | "tie" | "bye";

export interface SimRecapStarter {
  slot: SimSlot;
  player: SimGamePlayer | null;
  pts: number;
  flag: "bye" | "out" | null;
  stats?: Record<string, number> | null;
}

export interface SimRecapYourGame {
  opponent_id: string;
  opponent_name: string;
  your_pts: number;
  opp_pts: number;
  result: SimGameResultKind;
  starters: SimRecapStarter[];
  bench?: SimRecapStarter[];
  optimal_pts?: number;
  efficiency?: number;
}

export interface SimRecapScore {
  home: string;
  away: string;
  home_pts: number | null;
  away_pts: number | null;
  winner: string | null;
}

export interface SimWeekRecap {
  week: number;
  kind: "regular" | "playoff";
  round: number | null;
  your_game: SimRecapYourGame | null;
  scores: SimRecapScore[];
  standings?: SimStandingRow[];
  waivers?: { team_id: string; name: string; add: SimGamePlayer; drop: SimGamePlayer | null; ok: boolean; reason: string }[];
  transactions?: SimTransaction[];
  injuries?: { player: SimGamePlayer; weeks: number; team_id: string; is_yours: boolean }[];
  mvp?: { player: SimGamePlayer; pts: number } | null;
  bust?: { player: SimGamePlayer; pts: number } | null;
  auto_filled_slots?: unknown[];
  season_complete: boolean;
  champion: string | null;
  next_week: number | null;
}

export interface SimAdvanceResponse extends SimGameEnvelope {
  recap?: SimWeekRecap;
  also_played?: SimWeekRecap[];
  replayed?: boolean;
  game?: SimGame;
}

export interface SimStandingRow {
  rank: number;
  team_id: string;
  name: string;
  owner?: string;
  is_you: boolean;
  persona_id?: string;
  wins: number;
  losses: number;
  ties: number;
  pf: number;
  pa: number;
  streak?: string;
  seed?: number | null;
  playoff_status?: string;
}

/** A player a feed row names (role: add / drop / give / get), enough for a photo row. */
export interface SimTransactionPlayer {
  role: "add" | "drop" | "give" | "get";
  id: string;
  headshot_id?: string | null;
  name: string;
  pos: SimPos;
  team?: string | null;
}

export interface SimTransaction {
  players?: SimTransactionPlayer[];
  week?: number;
  type?: string;
  kind?: string;
  text?: string;
  team_id?: string;
  [key: string]: unknown;
}

export interface SimLeagueTeam {
  team_id: string;
  name: string;
  owner?: string;
  persona: SimGamePersona;
  is_you: boolean;
  power_rank: number;
  avg_age: number;
}

export interface SimLeagueResponse extends SimGameEnvelope {
  standings?: SimStandingRow[];
  schedule?: { week: number; kind: string; games: SimRecapScore[] }[];
  transactions?: SimTransaction[];
  teams?: SimLeagueTeam[];
  playoffs?: { seeds: unknown[]; rounds: unknown[]; champion: string | null } | null;
}

export interface SimGameGradeSummary {
  record?: string;
  finish?: number;
  points_rank?: number;
  playoff_result?: string;
  lineup_efficiency?: number;
  luck_wins?: number;
  draft_grade?: string;
}

export interface SimGameGrade {
  letter?: string | null;
  score?: number;
  grade_points?: number;
  components?: { key?: string; label?: string; score?: number; weight?: number }[] | Record<string, number>;
  /** The backend sends an object; older clients assumed a string. Never render it directly. */
  summary?: SimGameGradeSummary | string | null;
}

export interface SimGameDecision {
  title?: string;
  kind?: string;
  detail?: string;
  impact?: Record<string, unknown>;
  [key: string]: unknown;
}

export interface SimGameResult {
  /** The backend sends {team_id, name}; null when nobody won (e.g. a game with no playoff). */
  champion?: { team_id?: string; name?: string } | string | null;
  final_standings?: (SimStandingRow & { playoff_result?: string })[] | null;
  grade?: SimGameGrade | null;
  decisions_that_mattered?: SimGameDecision[] | null;
  draft?: { grade?: string; picks_value?: unknown[] } | null;
  user?: Record<string, unknown> | null;
  /** Season in Review payload (modules/sim/game_review.py); absent on results stored before it existed. */
  review?: Record<string, unknown> | null;
}

/** A render-safe view of a stored result: every field is present, every value is a primitive. */
export interface SimGameResultView {
  letter: string;
  summaryText: string;
  championId: string | null;
  championName: string | null;
  standings: (SimStandingRow & { playoff_result?: string })[];
  decisions: SimGameDecision[];
  mine: (SimStandingRow & { playoff_result?: string }) | null;
}

export function simGradeSummaryText(summary: SimGameGrade["summary"]): string {
  if (typeof summary === "string") return summary;
  if (!summary || typeof summary !== "object") return "";
  const parts: string[] = [];
  if (summary.record) parts.push(`Record ${summary.record}`);
  if (typeof summary.finish === "number") parts.push(`finished ${summary.finish}${simOrdinalSuffix(summary.finish)}`);
  if (typeof summary.points_rank === "number") parts.push(`${summary.points_rank}${simOrdinalSuffix(summary.points_rank)} in points`);
  if (typeof summary.lineup_efficiency === "number") parts.push(`${Math.round(summary.lineup_efficiency * 100)}% lineup efficiency`);
  if (summary.draft_grade) parts.push(`draft grade ${summary.draft_grade}`);
  return parts.length ? `${parts.join(", ")}.` : "";
}

function simOrdinalSuffix(n: number): string {
  const mod100 = n % 100;
  if (mod100 >= 11 && mod100 <= 13) return "th";
  return ({ 1: "st", 2: "nd", 3: "rd" } as Record<number, string>)[n % 10] ?? "th";
}

export function normalizeSimResult(raw: SimGameResult | null | undefined): SimGameResultView {
  const standings = Array.isArray(raw?.final_standings) ? raw.final_standings.filter(Boolean) : [];
  const champ = raw?.champion;
  const championId = typeof champ === "string" ? champ : champ && typeof champ === "object" && champ.team_id != null ? String(champ.team_id) : null;
  const named = championId ? standings.find((row) => String(row.team_id) === championId) : undefined;
  const championName = champ && typeof champ === "object" && champ.name ? String(champ.name) : named?.name ?? null;
  return {
    letter: typeof raw?.grade?.letter === "string" ? raw.grade.letter : "",
    summaryText: simGradeSummaryText(raw?.grade?.summary),
    championId,
    championName,
    standings,
    decisions: Array.isArray(raw?.decisions_that_mattered) ? raw.decisions_that_mattered.filter(Boolean) : [],
    mine: standings.find((row) => row.is_you) ?? null,
  };
}

export interface SimGameResultResponse extends SimGameEnvelope {
  result?: SimGameResult;
}

export interface SimGameResponse extends SimGameEnvelope {
  game?: SimGame;
  draft?: SimDraftState;
}

// ---------------------------------------------------------------------------
// Reasons and gating

const REASON_COPY: Record<string, string> = {
  premium_required: "Fantasy Sim is a Pro feature.",
  sim_storage_unavailable: "Saving games is temporarily unavailable. Try again in a little while.",
  players_unavailable: "The player pool could not be built right now. Try again in a moment.",
  game_limit_reached: "You have reached your limit of saved games. Delete one to start another.",
  result_build_failed: "We could not grade this season. Your game is saved. Try again in a moment.",
  wrong_phase: "That is not available at this stage of the game.",
  not_your_turn: "It is not your turn to pick yet.",
  player_taken: "That player was just taken. Pick someone else.",
  roster_over_limit: "Your roster is over the limit. Cut players before you advance.",
  trade_deadline_passed: "The trade deadline has passed.",
  trades_closed: "Trades are closed during the playoffs.",
  duplicate_offer: "You already tried that exact offer this week.",
  partner_trade_limit: "That team has made all the trades it will make this season.",
  offer_invalid: "That offer is no longer valid. The players moved or it expired.",
  week_mismatch: "That week is not ready to play. Reload the game.",
  not_complete: "The season is not over yet.",
  conflict: "The game changed somewhere else. We reloaded it. Try again.",
  sim_busy: "The simulator is busy right now. Try again in a few seconds.",
  team_not_found: "We could not tell which team is yours in that league. Pick it from the list.",
  league_unavailable: "That league could not be read right now. Try again in a moment.",
  league_platform_unsupported: "Only Sleeper leagues can start a game for now.",
  league_size_unsupported: "That league has a size the game cannot play (it needs an even number of teams, 4 to 16).",
  league_lineup_unsupported: "That league's lineup has nothing the game can play (it only models QB, RB, WR, TE, flex, K and DEF).",
  league_scoring_unavailable: "That league's scoring could not be read.",
  def_unavailable: "Team defenses are not available right now. Turn off DEF in Advanced options.",
  k_unavailable: "Kickers are not available right now. Turn off K in Advanced options.",
};

/** User-facing sentence for a backend `reason` (empty string for success). */
export function simGameReasonMessage(reason: string | undefined | null, body?: SimGameEnvelope | null): string {
  if (!reason) return "";
  if (reason === "roster_over_limit" && body?.cuts_needed) {
    const n = body.cuts_needed;
    return `Cut ${n} player${n === 1 ? "" : "s"} to get back to the roster limit before you advance.`;
  }
  return REASON_COPY[reason] ?? "Something went wrong. Try again.";
}

export type SimGameGate =
  | { kind: "ready" }
  | { kind: "premium"; upsell: SimGameUpsell | null; preview: SimGamePreview | null }
  | { kind: "unavailable"; cause: "off" | "storage" | "busy" }
  | { kind: "conflict" }
  | { kind: "blocked"; reason: string; message: string };

/**
 * Classify any response body (or thrown ApiError-like) into what the screen
 * should do. `premium_required` is a normal 200, not an error: the call did
 * nothing and the caller shows the upsell while reads keep working.
 */
export function simGameGate(body: SimGameEnvelope | null | undefined): SimGameGate {
  if (!body) return { kind: "unavailable", cause: "off" };
  const reason = body.reason ?? "";
  if (reason === "premium_required" || reason === "game_limit_reached") {
    if (reason === "game_limit_reached" && body.is_premium !== false) {
      return { kind: "blocked", reason, message: simGameReasonMessage(reason, body) };
    }
    return { kind: "premium", upsell: body.upsell ?? null, preview: body.preview ?? null };
  }
  if (reason === "sim_storage_unavailable") return { kind: "unavailable", cause: "storage" };
  if (reason === "conflict") return { kind: "conflict" };
  if (reason === "sim_busy") return { kind: "unavailable", cause: "busy" };
  if (reason) return { kind: "blocked", reason, message: body.message || simGameReasonMessage(reason, body) };
  return { kind: "ready" };
}

/** Same classification for a thrown error (404 = flag off, 409 = conflict, 503 = busy). */
export function simGameErrorGate(error: unknown): SimGameGate | null {
  if (typeof error !== "object" || error === null) return null;
  const e = error as { status?: number; code?: string };
  if (e.status === 404) return { kind: "unavailable", cause: "off" };
  if (e.status === 409) return { kind: "conflict" };
  if (e.status === 503 || e.code === "server_busy") return { kind: "unavailable", cause: "busy" };
  return null;
}

export function simGameUnavailableCopy(cause: "off" | "storage" | "busy"): { title: string; subtitle: string } {
  if (cause === "storage") {
    return {
      title: "Fantasy Sim is temporarily unavailable",
      subtitle: "It is switched on, but we cannot save games right now. Your progress is safe. Try again in a little while.",
    };
  }
  if (cause === "busy") {
    return {
      title: "The simulator is busy",
      subtitle: "A lot of games are running. Give it a few seconds and try again.",
    };
  }
  return {
    title: "Fantasy Sim is coming soon",
    subtitle: "Draft a team, run a whole season against AI managers, and get graded. It is not switched on yet. Check back soon.",
  };
}

// ---------------------------------------------------------------------------
// Stage machine: which screen a game belongs on

export type SimGameStage = "draft" | "week" | "playoffs" | "final";

export function simGameStage(game: Pick<SimGame, "status">): SimGameStage {
  switch (game.status) {
    case "drafting":
      return "draft";
    case "playoffs":
      return "playoffs";
    case "complete":
      return "final";
    default:
      return "week";
  }
}

/** True once the free preview is used up (every write answers premium_required). */
export function simGamePaywalled(preview: SimGamePreview | null | undefined): boolean {
  return Boolean(preview?.paywalled);
}

/** One line for the preview banner; null for Pro (no banner). */
export function simGamePreviewLine(preview: SimGamePreview | null | undefined): string | null {
  if (!preview) return null;
  if (preview.paywalled) {
    return `Free preview over. Your season is paused at week ${preview.paywall_week}. Go Pro to pick it up right here.`;
  }
  const n = preview.weeks_left;
  if (n <= 0) return `Free preview. Week ${preview.paywall_week} needs Pro.`;
  return `Free preview: ${n} week${n === 1 ? "" : "s"} left to play before Pro.`;
}

/** Next week would hit the paywall: warn before the tap. */
export function simGameAdvanceHitsPaywall(preview: SimGamePreview | null | undefined, game: Pick<SimGame, "week">): boolean {
  if (!preview) return false;
  return preview.paywalled || game.week + 1 >= preview.paywall_week;
}

// ---------------------------------------------------------------------------
// Advance blockers

export interface SimAdvanceBlocker {
  code: "cuts" | "paywalled" | "no_game";
  message: string;
}

/** Things that stop "Advance week" before the call (warnings do not block). */
export function simAdvanceBlockers(game: SimGame | null | undefined, preview?: SimGamePreview | null): SimAdvanceBlocker[] {
  if (!game) return [{ code: "no_game", message: "No game loaded." }];
  const out: SimAdvanceBlocker[] = [];
  if (simGamePaywalled(preview)) {
    out.push({ code: "paywalled", message: "Free preview is over. Go Pro to keep playing." });
  }
  const cuts = game.pending?.cuts_needed ?? 0;
  if (cuts > 0) {
    out.push({ code: "cuts", message: simGameReasonMessage("roster_over_limit", { cuts_needed: cuts }) });
  }
  return out;
}

/** Soft warnings shown by the Advance button (the engine allows all of these). */
export function simAdvanceWarnings(game: SimGame | null | undefined): string[] {
  if (!game?.pending) return [];
  const out: string[] = [];
  const w = game.pending.lineup_warnings;
  if (w > 0) out.push(`${w} lineup issue${w === 1 ? "" : "s"}: a bye or injured starter scores 0.`);
  if (game.pending.inbox > 0) out.push(`${game.pending.inbox} trade offer${game.pending.inbox === 1 ? "" : "s"} will expire.`);
  return out;
}

export function simAdvanceLabel(game: Pick<SimGame, "phase" | "week" | "settings">): string {
  if (game.phase === "playoffs") return `Play playoff week ${game.week}`;
  if (game.phase === "complete") return "Season complete";
  return `Advance to week ${game.week + 1}`;
}

// ---------------------------------------------------------------------------
// Draft helpers

export const SIM_QUEUE_MAX = 30;
export const SIM_POSITIONS: SimPos[] = ["QB", "RB", "WR", "TE", "K", "DEF"];

/** Positions a league's player pool contains: no kickers without a K slot, no defenses without a DEF slot. */
export function simPositionsFor(slots: SimSlot[] | undefined): SimPos[] {
  const list = slots ?? [];
  return SIM_POSITIONS.filter((pos) => (pos !== "K" && pos !== "DEF") || list.includes(pos));
}

/** Positions that are one-per-roster and never traded (kickers, defenses). */
export function simTradable(pos: SimPos): boolean {
  return pos !== "K" && pos !== "DEF";
}

export interface SimQueueState {
  ids: string[];
}

export type SimQueueAction =
  | { type: "set"; ids: string[] }
  | { type: "add"; id: string }
  | { type: "remove"; id: string }
  | { type: "move"; id: string; delta: -1 | 1 }
  | { type: "prune"; taken: string[] };

/** Queue reducer: a unique, capped, ordered list. Pure, so it is testable and shared with the app. */
export function simQueueReducer(state: SimQueueState, action: SimQueueAction): SimQueueState {
  switch (action.type) {
    case "set":
      return { ids: dedupe(action.ids).slice(0, SIM_QUEUE_MAX) };
    case "add":
      if (state.ids.includes(action.id) || state.ids.length >= SIM_QUEUE_MAX) return state;
      return { ids: [...state.ids, action.id] };
    case "remove":
      return state.ids.includes(action.id) ? { ids: state.ids.filter((id) => id !== action.id) } : state;
    case "move": {
      const from = state.ids.indexOf(action.id);
      const to = from + action.delta;
      if (from < 0 || to < 0 || to >= state.ids.length) return state;
      const ids = [...state.ids];
      [ids[from], ids[to]] = [ids[to], ids[from]];
      return { ids };
    }
    case "prune": {
      const taken = new Set(action.taken);
      const ids = state.ids.filter((id) => !taken.has(id));
      return ids.length === state.ids.length ? state : { ids };
    }
  }
}

function dedupe(ids: string[]): string[] {
  return ids.filter((id, index) => ids.indexOf(id) === index);
}

export type SimPlayerSort = "projection" | "value" | "adp" | "age" | "name" | "last_week" | "season";

export const SIM_SORT_OPTIONS: { value: SimPlayerSort; label: string }[] = [
  { value: "projection", label: "Projection" },
  { value: "value", label: "Value" },
  { value: "adp", label: "ADP" },
  { value: "season", label: "Season pts" },
  { value: "last_week", label: "Last week" },
  { value: "age", label: "Age" },
  { value: "name", label: "Name" },
];

export type SimPlayerStatusFilter = "" | "available" | "rostered" | "mine" | "injured" | "bye";

export const SIM_STATUS_OPTIONS: { value: SimPlayerStatusFilter; label: string }[] = [
  { value: "", label: "All" },
  { value: "available", label: "Free agents" },
  { value: "mine", label: "Mine" },
  { value: "rostered", label: "Rostered" },
  { value: "injured", label: "Injured" },
  { value: "bye", label: "On bye" },
];

export interface SimPlayerFilter {
  q: string;
  pos: SimPos | "";
  status: SimPlayerStatusFilter;
  sort: SimPlayerSort;
  page: number;
}

export const SIM_PAGE_SIZE = 40;

export function simDefaultFilter(overrides: Partial<SimPlayerFilter> = {}): SimPlayerFilter {
  return { q: "", pos: "", status: "", sort: "projection", page: 1, ...overrides };
}

export type SimFilterAction =
  | { type: "q"; value: string }
  | { type: "pos"; value: SimPos | "" }
  | { type: "status"; value: SimPlayerStatusFilter }
  | { type: "sort"; value: SimPlayerSort }
  | { type: "page"; value: number }
  | { type: "reset"; overrides?: Partial<SimPlayerFilter> };

/** Changing any filter returns to page 1; changing only the page keeps the rest. */
export function simFilterReducer(state: SimPlayerFilter, action: SimFilterAction): SimPlayerFilter {
  switch (action.type) {
    case "q":
      return state.q === action.value ? state : { ...state, q: action.value, page: 1 };
    case "pos":
      return state.pos === action.value ? state : { ...state, pos: action.value, page: 1 };
    case "status":
      return state.status === action.value ? state : { ...state, status: action.value, page: 1 };
    case "sort":
      return state.sort === action.value ? state : { ...state, sort: action.value, page: 1 };
    case "page":
      return { ...state, page: Math.max(1, Math.floor(action.value)) };
    case "reset":
      return simDefaultFilter(action.overrides);
  }
}

/** Query string for the players / draft endpoints (empty values are omitted). */
export function simFilterQuery(filter: SimPlayerFilter, pageSize = SIM_PAGE_SIZE, includeStatusSort = true): string {
  const params: [string, string][] = [];
  if (filter.q.trim()) params.push(["q", filter.q.trim()]);
  if (filter.pos) params.push(["pos", filter.pos]);
  if (includeStatusSort) {
    if (filter.status) params.push(["status", filter.status]);
    if (filter.sort && filter.sort !== "projection") params.push(["sort", filter.sort]);
  }
  params.push(["page", String(filter.page)], ["page_size", String(pageSize)]);
  return params.map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`).join("&");
}

export function simPageCount(total: number, pageSize: number): number {
  return Math.max(1, Math.ceil(total / Math.max(1, pageSize)));
}

/** "Round 3, pick 2" from a 1-based overall pick number. */
export function simPickLabel(pickNo: number, teams: number): string {
  const round = Math.floor((pickNo - 1) / teams) + 1;
  const inRound = ((pickNo - 1) % teams) + 1;
  return `Round ${round}, pick ${inRound}`;
}

/** Status line over the board: whose pick it is and how far away yours is. */
export function simDraftClockLine(draft: Pick<SimDraftState, "status" | "on_the_clock" | "picks_until_you" | "pick_no" | "total_picks">): string {
  if (draft.status === "complete") return "Draft complete.";
  if (draft.on_the_clock?.is_you) return "You are on the clock.";
  const n = draft.picks_until_you;
  const who = draft.on_the_clock?.name ?? "An AI manager";
  if (n > 0) return `${who} is picking. Your pick is ${n} pick${n === 1 ? "" : "s"} away.`;
  return `${who} is picking.`;
}

/** Roster needs for the draft side panel: filled vs required per position. */
export function simRosterNeeds(roster: Pick<SimGamePlayer, "pos">[], slots: SimSlot[]): { pos: SimPos; have: number; starters: number }[] {
  const starters: Record<string, number> = {};
  for (const slot of slots) {
    if (SIM_FLEX_ELIGIBLE[slot]) continue;
    starters[slot] = (starters[slot] ?? 0) + 1;
  }
  return simPositionsFor(slots).map((pos) => ({
    pos,
    have: roster.filter((p) => p.pos === pos).length,
    starters: starters[pos] ?? 0,
  }));
}

/** Pick value label: positive = a steal against ADP. */
export function simValueOverAdpLabel(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "";
  if (Math.abs(value) < 0.5) return "On ADP";
  return value > 0 ? `Steal +${value.toFixed(0)}` : `Reach ${value.toFixed(0)}`;
}

export function simValueOverAdpTone(value: number | null | undefined): SimGameTone {
  if (value == null || Math.abs(value) < 0.5) return "muted";
  return value > 0 ? "success" : "warning";
}

// ---------------------------------------------------------------------------
// Lineup helpers

export type SimGameTone = "success" | "accent" | "warning" | "danger" | "muted";

/** Positions each flex slot accepts (mirrors modules/sim/types.py FLEX_SLOTS). */
const SIM_FLEX_ELIGIBLE: Partial<Record<SimSlot, SimPos[]>> = {
  REC_FLEX: ["WR", "TE"],
  FLEX: ["RB", "WR", "TE"],
  SUPER_FLEX: ["QB", "RB", "WR", "TE"],
};

/** Can a player of `pos` start in `slot`? Mirrors the engine's slot rules. */
export function simSlotAccepts(slot: SimSlot, pos: SimPos): boolean {
  const flex = SIM_FLEX_ELIGIBLE[slot];
  if (flex) return flex.includes(pos);
  return slot === pos;
}

/** Slots in order with an eligible bench/other-slot candidate list for a tapped slot. */
export function simSlotCandidates(
  slot: SimSlot,
  slots: SimLineupSlot[],
  bench: SimGamePlayer[],
): { player: SimGamePlayer; from: "bench" | "slot" }[] {
  const out: { player: SimGamePlayer; from: "bench" | "slot" }[] = [];
  for (const p of bench) if (simSlotAccepts(slot, p.pos)) out.push({ player: p, from: "bench" });
  for (const s of slots) {
    if (s.player && simSlotAccepts(slot, s.player.pos)) out.push({ player: s.player, from: "slot" });
  }
  return out.sort((a, b) => b.player.projection - a.player.projection);
}

export interface SimLineupEdit {
  slots: SimLineupSlot[];
  bench: SimGamePlayer[];
}

/**
 * Put `player` into slot index `index`. If he already starts elsewhere the two
 * slots swap when the displaced player fits there; otherwise that slot empties.
 * The displaced starter goes to the bench. Pure: returns a new edit.
 */
export function simAssignSlot(edit: SimLineupEdit, index: number, player: SimGamePlayer | null): SimLineupEdit {
  const slots = edit.slots.map((s) => ({ ...s }));
  let bench = [...edit.bench];
  const target = slots[index];
  if (!target) return edit;
  const displaced = target.player;
  if (player && !simSlotAccepts(target.slot, player.pos)) return edit;
  const otherIndex = player ? slots.findIndex((s, i) => i !== index && s.player?.id === player.id) : -1;
  if (player) bench = bench.filter((p) => p.id !== player.id);
  target.player = player;
  if (otherIndex >= 0) {
    const other = slots[otherIndex];
    if (displaced && simSlotAccepts(other.slot, displaced.pos)) other.player = displaced;
    else {
      other.player = null;
      if (displaced) bench.push(displaced);
    }
  } else if (displaced && displaced.id !== player?.id) {
    bench.push(displaced);
  }
  return { slots, bench };
}

/** Body for PUT /lineup: exactly the league's slots, in order. */
export function simLineupPayload(slots: SimLineupSlot[]): { slots: { slot: SimSlot; player_id: string | null }[] } {
  return { slots: slots.map((s) => ({ slot: s.slot, player_id: s.player?.id ?? null })) };
}

export function simLineupDirty(a: SimLineupSlot[], b: SimLineupSlot[]): boolean {
  if (a.length !== b.length) return true;
  return a.some((s, i) => s.slot !== b[i].slot || (s.player?.id ?? null) !== (b[i].player?.id ?? null));
}

/** Label for a numbered slot ("RB1", "RB2"); single slots keep their name. */
export function simSlotLabels(slots: { slot: SimSlot }[]): string[] {
  const counts: Record<string, number> = {};
  for (const s of slots) counts[s.slot] = (counts[s.slot] ?? 0) + 1;
  const seen: Record<string, number> = {};
  return slots.map((s) => {
    seen[s.slot] = (seen[s.slot] ?? 0) + 1;
    return counts[s.slot] > 1 ? `${s.slot}${seen[s.slot]}` : s.slot;
  });
}

export function simWarningText(warning: SimLineupWarning, playerName?: string): string {
  const who = playerName ?? "Your starter";
  if (warning.code === "bye") return `${who} is on a bye and will score 0.`;
  if (warning.code === "out") return `${who} is out and will score 0.`;
  return `Your ${warning.slot} slot is empty.`;
}

/** Short status text/tone for a player's availability. */
export function simPlayerStatusLabel(player: Pick<SimGamePlayer, "status" | "out_weeks" | "bye_week">): { label: string; tone: SimGameTone } | null {
  if (player.status === "out") {
    return { label: player.out_weeks > 0 ? `Out ${player.out_weeks}w` : "Out", tone: "danger" };
  }
  if (player.status === "bye") return { label: "Bye", tone: "warning" };
  return null;
}

// ---------------------------------------------------------------------------
// Waivers, trades

export interface SimClaimDraft {
  add: SimGamePlayer | null;
  drop: SimGamePlayer | null;
  startSlot: SimSlot | null;
}

/** Roster has room for the add without a drop. */
export function simNeedsDrop(rosterSize: number, rosterLimit: number, queuedAdds = 0): boolean {
  return rosterSize + queuedAdds >= rosterLimit;
}

export function simClaimPayload(draft: SimClaimDraft): { add: string; drop: string | null; start_slot: SimSlot | null } | null {
  if (!draft.add) return null;
  return { add: draft.add.id, drop: draft.drop?.id ?? null, start_slot: draft.startSlot };
}

export const SIM_TRADE_MAX_PER_SIDE = 3;

export interface SimTradeDraft {
  partner: string | null;
  give: string[];
  get: string[];
}

export type SimTradeAction =
  | { type: "partner"; teamId: string | null }
  | { type: "toggle"; side: "give" | "get"; id: string }
  | { type: "load"; give: string[]; get: string[] }
  | { type: "clear" };

export const SIM_TRADE_EMPTY: SimTradeDraft = { partner: null, give: [], get: [] };

/** Trade builder reducer: switching partner clears the incoming side; sides cap at 3. */
export function simTradeReducer(state: SimTradeDraft, action: SimTradeAction): SimTradeDraft {
  switch (action.type) {
    case "partner":
      return state.partner === action.teamId ? state : { partner: action.teamId, give: state.give, get: [] };
    case "toggle": {
      const list = state[action.side];
      if (list.includes(action.id)) return { ...state, [action.side]: list.filter((id) => id !== action.id) };
      if (list.length >= SIM_TRADE_MAX_PER_SIDE) return state;
      return { ...state, [action.side]: [...list, action.id] };
    }
    case "load":
      return { ...state, give: action.give.slice(0, SIM_TRADE_MAX_PER_SIDE), get: action.get.slice(0, SIM_TRADE_MAX_PER_SIDE) };
    case "clear":
      return SIM_TRADE_EMPTY;
  }
}

/** A trade can be previewed once a partner is picked and each side has 1-3 players. */
export function simTradeReady(draft: SimTradeDraft): boolean {
  return Boolean(draft.partner) && draft.give.length > 0 && draft.get.length > 0;
}

export function simTradeKey(draft: SimTradeDraft): string {
  return `${draft.partner ?? ""}|${[...draft.give].sort().join(",")}|${[...draft.get].sort().join(",")}`;
}

export function simTradePayload(draft: SimTradeDraft): { partner: string; give: string[]; get: string[] } | null {
  if (!simTradeReady(draft) || !draft.partner) return null;
  return { partner: draft.partner, give: draft.give, get: draft.get };
}

export function simTradeDecisionTone(decision: SimTradeDecision): SimGameTone {
  if (decision === "accept") return "success";
  if (decision === "counter") return "warning";
  return "danger";
}

export function simTradeDecisionLabel(decision: SimTradeDecision): string {
  if (decision === "accept") return "They would accept";
  if (decision === "counter") return "They would counter";
  return "They would decline";
}

/** Can the user send the offer right now (deadline, phase)? Returns the reason when not. */
export function simTradeClosedReason(game: Pick<SimGame, "can_trade" | "phase" | "trade_deadline_week">): string | null {
  if (game.can_trade) return null;
  if (game.phase === "playoffs") return simGameReasonMessage("trades_closed");
  return simGameReasonMessage("trade_deadline_passed");
}

// ---------------------------------------------------------------------------
// Formatting

export function simFmtPts(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "-";
  return value.toFixed(1);
}

export function simFmtRecord(line: { wins: number; losses: number; ties: number }): string {
  return line.ties ? `${line.wins}-${line.losses}-${line.ties}` : `${line.wins}-${line.losses}`;
}

export function simFmtValue(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "-";
  return value.toFixed(0);
}

export function simFmtAge(age: number | null | undefined): string {
  if (age == null || Number.isNaN(age)) return "";
  return `${Math.floor(age)}`;
}

/** Projection range text: "17.4 (9.1-27.7)". */
export function simFmtProjection(player: Pick<SimGamePlayer, "projection" | "floor" | "ceiling">): string {
  return `${simFmtPts(player.projection)} (${simFmtPts(player.floor)}-${simFmtPts(player.ceiling)})`;
}

/** Anything a sim list can show a player row for: the full row or a brief ref. */
export type SimPlayerRef = Pick<SimGamePlayer, "id" | "name" | "pos"> & Partial<Pick<SimGamePlayer, "headshot_id" | "team" | "age" | "bye_week" | "status" | "out_weeks">>;

/** The id the shared avatar fetches a Sleeper photo with (null: show initials). */
export function simHeadshotId(player: Pick<SimPlayerRef, "id" | "headshot_id">): string | null {
  if (player.headshot_id) return player.headshot_id;
  return player.headshot_id === undefined && /^\d+$/.test(player.id) ? player.id : null;
}

/** Initials for the avatar fallback: a defense shows its team code, a person first + last initial. */
export function simPlayerInitials(player: Pick<SimPlayerRef, "name" | "pos" | "team">): string {
  if (player.pos === "DEF") return (player.team ?? player.name).slice(0, 3).toUpperCase();
  const words = player.name.replace(/[^A-Za-z\s'-]/g, " ").split(/\s+/).filter(Boolean);
  if (words.length === 0) return "";
  if (words.length === 1) return words[0][0].toUpperCase();
  return (words[0][0] + words[words.length - 1][0]).toUpperCase();
}

/**
 * A lineup row already shows its slot ("RB1"); the player's own position
 * chip is only worth showing when it adds information (FLEX, SUPER_FLEX and
 * other multi-position slots), not when it just repeats the slot's position.
 */
export function simSlotRepeatsPosition(slot: string, pos: string): boolean {
  return slot.toUpperCase() === pos.toUpperCase();
}

/** NFL team + age subline for a player row. */
export function simPlayerSubline(player: Partial<Pick<SimGamePlayer, "team" | "age" | "bye_week">>): string {
  const parts: string[] = [];
  if (player.team) parts.push(player.team);
  const age = simFmtAge(player.age ?? null);
  if (age) parts.push(`Age ${age}`);
  if (player.bye_week) parts.push(`Bye ${player.bye_week}`);
  return parts.join(" · ");
}

export function simOwnerLabel(owner: SimPlayerOwner | null | undefined): string {
  if (!owner) return "";
  if (owner.type === "you") return "Your team";
  if (owner.type === "free_agent") return "Free agent";
  return owner.name ?? "AI team";
}

export function simOwnerTone(owner: SimPlayerOwner | null | undefined): SimGameTone {
  if (!owner) return "muted";
  if (owner.type === "you") return "accent";
  if (owner.type === "free_agent") return "success";
  return "muted";
}

export function simResultLabel(result: SimGameResultKind | undefined): string {
  if (result === "win") return "Win";
  if (result === "loss") return "Loss";
  if (result === "tie") return "Tie";
  if (result === "bye") return "Bye";
  return "";
}

export function simResultTone(result: SimGameResultKind | undefined): SimGameTone {
  if (result === "win") return "success";
  if (result === "loss") return "danger";
  if (result === "tie") return "warning";
  return "muted";
}

/** Heading for the week the game is on. */
export function simWeekHeading(game: Pick<SimGame, "phase" | "week" | "round" | "settings">): string {
  if (game.phase === "draft") return "Draft";
  if (game.phase === "complete") return "Final";
  if (game.phase === "playoffs") return `${simPlayoffRoundLabel(game.week, game.settings)} · Week ${game.week}`;
  return `Week ${game.week} of ${game.settings.regular_weeks}`;
}

/** Playoff week to round name: the last playoff week is the final. */
export function simPlayoffRoundLabel(week: number, settings: Pick<SimGameSettings, "regular_weeks" | "playoff_weeks">): string {
  const index = week - settings.regular_weeks; // 1-based within playoffs
  if (index >= settings.playoff_weeks) return "Championship";
  if (index === settings.playoff_weeks - 1) return "Semifinals";
  return "Quarterfinals";
}

export function simGradeTone(letter: string | null | undefined): SimGameTone {
  const first = (letter ?? "").trim().charAt(0).toUpperCase();
  if (first === "A") return "success";
  if (first === "B") return "accent";
  if (first === "C") return "warning";
  if (first === "D" || first === "F") return "danger";
  return "muted";
}

export function simPlayoffStatusLabel(status: string | undefined): string {
  switch (status) {
    case "in":
      return "In";
    case "clinched":
      return "Clinched";
    case "bye":
      return "Bye";
    case "out":
      return "Out";
    case "eliminated":
      return "Out";
    default:
      return "";
  }
}

/** Playoff outcome color: champion green, a deep run blue, early exit amber, missed red. */
export function simPlayoffOutcomeTone(result: string | undefined): SimGameTone {
  switch (result) {
    case "champion":
      return "success";
    case "runner_up":
    case "semifinal":
      return "accent";
    case "missed":
      return "danger";
    case "lost_round_1":
    case "lost_round_2":
    case "lost_round_3":
      return "warning";
    default:
      return "muted";
  }
}

export function simPlayoffResultLabel(result: string | undefined): string {
  switch (result) {
    case "champion":
      return "Champion";
    case "runner_up":
      return "Runner-up";
    case "semifinal":
    case "semifinalist":
      return "Semifinals";
    case "quarterfinal":
      return "Quarterfinals";
    case "lost_round_1":
      return "Lost in round 1";
    case "lost_round_2":
      return "Lost in round 2";
    case "lost_round_3":
      return "Lost in round 3";
    case "missed":
    case "missed_playoffs":
      return "Missed playoffs";
    default:
      return result ? result.replace(/_/g, " ") : "";
  }
}

/** Plain-language one-liner for a team-vs-team matchup preview. */
export function simMatchupLine(week: SimGameThisWeek | null | undefined): string {
  if (!week) return "";
  if (week.bye || !week.opponent) return "You have a bye this week.";
  const diff = week.your_projection - week.opponent_projection;
  const favored = Math.abs(diff) < 1 ? "a toss-up" : diff > 0 ? `you are favored by ${diff.toFixed(1)}` : `you are ${Math.abs(diff).toFixed(1)} behind`;
  return `vs ${week.opponent.name}: ${favored}.`;
}

/** Transaction feed row text from whatever the engine put in the row. */
export function simTransactionText(row: SimTransaction): string {
  if (typeof row.text === "string" && row.text) return row.text;
  const kind = row.type ?? row.kind ?? "move";
  return `${kind}`.replace(/_/g, " ");
}

/** Glyph + tone for a league transaction row: trade accent swap, waiver add green, drop red, injury red cross. */
export function simTransactionGlyph(row: Pick<SimTransaction, "type" | "kind">): { glyph: ReviewGlyph; tone: SimGameTone } {
  const kind = `${row.type ?? row.kind ?? ""}`.toLowerCase();
  if (kind.includes("trade")) return { glyph: "trade", tone: "accent" };
  if (kind.includes("injur")) return { glyph: "injury", tone: "danger" };
  if (kind.includes("drop") || kind.includes("cut") || kind.includes("release")) return { glyph: "bust", tone: "danger" };
  if (kind.includes("waiver") || kind.includes("add") || kind.includes("claim") || kind.includes("sign")) return { glyph: "waiver", tone: "success" };
  return { glyph: "stats", tone: "muted" };
}

/** Tone for a player's role inside a transaction: what a team got/added is green, what it sent/dropped is red. */
export function simTransactionRoleTone(role: string | undefined): SimGameTone {
  switch (role) {
    case "add":
    case "get":
      return "success";
    case "drop":
    case "give":
      return "danger";
    default:
      return "muted";
  }
}

/** Playoff-race chip color: in/clinched/bye green, out/eliminated red, anything else muted. */
export function simPlayoffStatusTone(status: string | undefined): SimGameTone {
  switch (status) {
    case "in":
    case "clinched":
    case "bye":
      return "success";
    case "out":
    case "eliminated":
      return "danger";
    case "bubble":
      return "warning";
    default:
      return "muted";
  }
}

/** Streak color from text like "W3" / "L2": wins green, losses red, anything else muted. */
export function simStreakTone(streak: string | undefined | null): SimGameTone {
  const first = (streak ?? "").trim().charAt(0).toUpperCase();
  if (first === "W") return "success";
  if (first === "L") return "danger";
  return "muted";
}

/** Matchup card tone from the projection gap: favored green, behind red, toss-up or bye amber/accent. */
export function simMatchupTone(week: SimGameThisWeek | null | undefined): SimGameTone {
  if (!week) return "muted";
  if (week.bye || !week.opponent) return "warning";
  const diff = week.your_projection - week.opponent_projection;
  if (Math.abs(diff) < 1) return "accent";
  return diff > 0 ? "success" : "danger";
}

/** Glyph for a notice by tone (shared by every in-game message strip). */
export function simNoticeGlyph(tone: SimGameTone): ReviewGlyph {
  switch (tone) {
    case "success":
      return "boom";
    case "danger":
      return "injury";
    case "warning":
      return "lineup";
    default:
      return "stats";
  }
}

/** Team id to display name from a league teams list. */
export function simTeamNameMap(teams: { team_id: string; name: string }[] | undefined): Record<string, string> {
  const map: Record<string, string> = {};
  for (const t of teams ?? []) map[t.team_id] = t.name;
  return map;
}

// ---------------------------------------------------------------------------
// Setup copy

export const SIM_SCORING_LABELS: Record<SimScoring, string> = { ppr: "PPR", half: "Half PPR", std: "Standard" };

/** The quick-start defaults, used until the options response says otherwise (12 teams, half PPR, standard lineup). */
export const SIM_SETUP_FALLBACK = {
  teams: 12,
  scoring: "half" as SimScoring,
  te_premium: 0,
  superflex: false,
  include_k: true,
  include_def: false,
  tiebreaker: "points_for" as SimTiebreaker,
  bench: 8,
  draftSpareSpots: 2,
};

export const SIM_TE_PREMIUM_LABELS: Record<number, string> = { 0: "Off", 0.5: "+0.5 per catch", 1: "+1 per catch" };

export interface SimSetupState {
  start: SimStartKind;
  /** Chosen real league (start === "league"). */
  leagueId: string;
  teams: number;
  scoring: SimScoring;
  tePremium: number;
  superflex: boolean;
  includeK: boolean;
  includeDef: boolean;
  tiebreaker: SimTiebreaker;
  bench: number;
  difficulty: SimDifficulty;
  slot: string;
  auto: boolean;
  /** Custom team name text (used when `nameChoice` is SIM_NAME_CUSTOM). */
  name: string;
  /** Fresh league: SIM_NAME_RANDOM, SIM_NAME_CUSTOM, or a preset name. */
  nameChoice: string;
  /** Start-from-league: the roster picked from the league's teams. Never a typed name. */
  rosterId: string;
}

export const SIM_NAME_RANDOM = "__random__";
export const SIM_NAME_CUSTOM = "__custom__";
export const SIM_TEAM_NAME_MAX = 40;

/** Every field at its quick-start default (from the API's options when loaded). */
export function simSetupDefaults(options: SimGameOptionsResponse | null | undefined): SimSetupState {
  const o = options?.options;
  return {
    start: "fresh",
    leagueId: "",
    teams: o?.teams.default ?? SIM_SETUP_FALLBACK.teams,
    scoring: o?.scoring.default ?? SIM_SETUP_FALLBACK.scoring,
    tePremium: o?.te_premium?.default ?? SIM_SETUP_FALLBACK.te_premium,
    superflex: o?.superflex?.default ?? SIM_SETUP_FALLBACK.superflex,
    includeK: o?.include_k?.default ?? SIM_SETUP_FALLBACK.include_k,
    includeDef: o?.include_def?.default ?? SIM_SETUP_FALLBACK.include_def,
    tiebreaker: o?.tiebreaker?.default ?? SIM_SETUP_FALLBACK.tiebreaker,
    bench: o?.bench?.default ?? SIM_SETUP_FALLBACK.bench,
    difficulty: o?.difficulty.default ?? "normal",
    slot: "",
    auto: o?.auto_lineup.default ?? false,
    name: "",
    nameChoice: SIM_NAME_RANDOM,
    rosterId: "",
  };
}

/** True when any "Advanced options" field differs from its default (so a collapsed section can say so). */
export function simSetupAdvancedChanged(state: SimSetupState, defaults: SimSetupState): number {
  const keys: (keyof SimSetupState)[] = ["scoring", "tePremium", "superflex", "includeK", "includeDef", "tiebreaker", "bench", "teams"];
  return keys.filter((key) => state[key] !== defaults[key]).length;
}

/**
 * Starting slots, roster size and draft rounds from the lineup toggles. Mirrors
 * modules/sim/game_types.py derive_layout (tests pin both to the same table):
 * QB, 2 RB, 2 WR, TE, FLEX, then SUPER_FLEX / K / DEF; roster = starters +
 * bench; the draft leaves `spare` spots open for the wire.
 */
export function simDeriveLayout(
  s: Pick<SimSetupState, "superflex" | "includeK" | "includeDef" | "bench">,
  baseSlots: SimSlot[] = ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX"],
  spare: number = SIM_SETUP_FALLBACK.draftSpareSpots,
): { slots: SimSlot[]; rosterLimit: number; rounds: number } {
  const slots: SimSlot[] = [...baseSlots];
  if (s.superflex) slots.push("SUPER_FLEX");
  if (s.includeK) slots.push("K");
  if (s.includeDef) slots.push("DEF");
  const rosterLimit = slots.length + s.bench;
  return { slots, rosterLimit, rounds: rosterLimit - spare };
}

/** The team name a fresh league sends: collapses runs of whitespace, keeps emoji and apostrophes, caps at the server limit. */
export function simCleanTeamName(raw: string): string {
  return Array.from(raw.split(/\s+/).filter(Boolean).join(" ")).slice(0, SIM_TEAM_NAME_MAX).join("");
}

/** The POST /v1/sim/games body for the form. "league" sends only what the league does not decide, and picks the team by roster_id. */
export function simSetupBody(state: SimSetupState): SimGameCreateBody {
  const common = { difficulty: state.difficulty, auto_lineup: state.auto, tiebreaker: state.tiebreaker };
  if (state.start === "league") return { ...common, start: "league", league_id: state.leagueId, ...(state.rosterId ? { roster_id: state.rosterId } : {}) };
  const custom = simCleanTeamName(state.name);
  const nameField =
    state.nameChoice === SIM_NAME_RANDOM
      ? { random_team_name: true }
      : state.nameChoice === SIM_NAME_CUSTOM
        ? custom
          ? { team_name: custom }
          : {}
        : { team_name: state.nameChoice };
  return {
    ...common,
    ...nameField,
    teams: state.teams,
    scoring: state.scoring,
    te_premium: state.tePremium,
    superflex: state.superflex,
    include_k: state.includeK,
    include_def: state.includeDef,
    bench: state.bench,
    mode: "redraft",
    user_slot: state.slot ? Number(state.slot) : null,
  };
}

/** Why the form cannot be submitted, or null. */
export function simSetupBlock(state: SimSetupState): string | null {
  if (state.start === "league") {
    if (!state.leagueId) return "Pick one of your leagues to start from.";
    if (!state.rosterId) return "Pick which team is yours.";
    return null;
  }
  if (state.nameChoice === SIM_NAME_CUSTOM && !simCleanTeamName(state.name)) return "Type a team name, or pick one from the list.";
  return null;
}

/** The roster to preselect once a league's teams load: the account's own, else none (the player must choose). */
export function simPreselectedRosterId(res: Pick<SimLeagueTeamsResponse, "you_roster_id" | "teams"> | null | undefined): string {
  const teams = res?.teams ?? [];
  const id = res?.you_roster_id ?? teams.find((t) => t.is_you)?.roster_id ?? "";
  return id && teams.some((t) => t.roster_id === id) ? id : "";
}

/** One line for a league team in the picker: name, owner, record and rank. */
export function simLeagueTeamLabel(team: SimImportTeam): string {
  const record = simFmtRecord(team);
  const bits = [team.team_name];
  if (team.owner_name && team.owner_name !== team.team_name) bits.push(team.owner_name);
  bits.push(record === "0-0" ? "no games yet" : record);
  if (record !== "0-0" && team.rank) bits.push(`#${team.rank}`);
  return bits.join(" · ");
}

/** Label for the preset-name picker entries. */
export function simTeamNameChoices(options: SimGameOptionsResponse | null | undefined): { value: string; label: string }[] {
  const presets = options?.options?.team_names?.values ?? [];
  return [
    { value: SIM_NAME_RANDOM, label: "Random" },
    ...presets.map((name) => ({ value: name, label: name })),
    { value: SIM_NAME_CUSTOM, label: "Custom name..." },
  ];
}

/** Saved leagues the game can start from: Sleeper leagues only (imported platforms carry a prefix). */
export function simImportableLeagues<T extends { league_id: string }>(rows: T[] | null | undefined): T[] {
  return (rows ?? []).filter((row) => typeof row.league_id === "string" && row.league_id !== "" && !row.league_id.includes(":"));
}

/** Plain words for the saved league settings ("14 teams · Half PPR · TE premium · Superflex"). */
export function simSettingsSummary(settings: Partial<SimGameSettings> | undefined): string {
  if (!settings) return "";
  const parts: string[] = [];
  if (settings.teams) parts.push(`${settings.teams} teams`);
  if (settings.scoring) parts.push(SIM_SCORING_LABELS[settings.scoring] ?? settings.scoring);
  if (settings.te_premium) parts.push(`TE premium +${settings.te_premium}`);
  if (settings.superflex) parts.push("Superflex");
  if (settings.include_def) parts.push("DEF");
  if (settings.include_k === false) parts.push("No kickers");
  if (settings.tiebreaker === "head_to_head") parts.push("Head-to-head tiebreak");
  if (settings.start === "league") parts.push("From your league");
  return parts.join(" · ");
}

/** What the setup tells the player about the league they are about to start. */
export function simSetupSummary(state: SimSetupState, layoutHint?: SimGameOptionsResponse["layout"]): string {
  if (state.start === "league") return "Your league's size, lineup, scoring and current rosters. A new 14-week season; nothing changes in your real league.";
  const layout = simDeriveLayout(state, layoutHint?.base_slots, layoutHint?.draft_spare_spots);
  return `${state.teams} teams, ${layout.rounds}-round snake draft. Starters: ${layout.slots.join(", ")}. Roster ${layout.rosterLimit}.`;
}

/** Difficulty only changes the AI managers; your own dice are identical at every level. */
export const SIM_DIFFICULTY_COPY: Record<SimDifficulty, { label: string; blurb: string }> = {
  easy: { label: "Easy", blurb: "Looser AI managers: more passive, more trade-friendly, slower on waivers." },
  normal: { label: "Normal", blurb: "A mixed league of AI managers. The default." },
  hard: { label: "Hard", blurb: "Sharper AI managers: tighter trades and smarter waiver moves." },
};

/** "You have 3 of 3 saved games" (singular when the limit is 1). */
export function simSavedGamesCount(gameCount: number, maxGames: number): string {
  return `You have ${gameCount} of ${maxGames} saved game${maxGames === 1 ? "" : "s"}`;
}

/** Why the New game button is unavailable, or null when you can start one. */
export function simNewGameBlock(gameCount: number, maxGames: number, isPremium: boolean | undefined): string | null {
  if (gameCount < maxGames) return null;
  const count = simSavedGamesCount(gameCount, maxGames);
  if (isPremium === false) return `${count}. Free includes ${maxGames} saved game. Delete it or go Pro for up to 3.`;
  return `${count}, the most allowed. Delete one to start another.`;
}

/** Names a saved game in the delete confirm (the list has no team name): stage, grade, league shape. */
export function simGameDeleteName(game: Pick<SimGameLite, "status" | "current_week" | "grade_letter" | "settings">): string {
  const shape = simSettingsSummary(game.settings);
  const line = simGameLiteLine(game);
  return shape ? `${line} (${shape})` : line;
}

/** Inline confirm copy for deleting one saved game. */
export function simGameDeleteConfirm(game: Pick<SimGameLite, "status" | "current_week" | "grade_letter" | "settings">): string {
  return `Delete ${simGameDeleteName(game)}? This cannot be undone. The whole season and its grade are removed.`;
}

/**
 * What to do when deleting a saved game from the list fails. 404 means it is
 * already gone (drop it from the list); 409/503 are retryable; anything else
 * shows the message. `refresh` asks the caller to reload the list.
 */
export function simGameDeleteFailure(error: unknown): { message: string; tone: "success" | "warning" | "danger"; remove: boolean; refresh: boolean } {
  const e = (typeof error === "object" && error !== null ? error : {}) as { status?: number; code?: string; message?: string };
  if (e.status === 404) return { message: "That game was already deleted.", tone: "warning", remove: true, refresh: true };
  if (e.status === 409) return { message: "The game changed somewhere else. We reloaded your games. Try again.", tone: "warning", remove: false, refresh: true };
  if (e.status === 503 || e.code === "server_busy") return { message: "The simulator is busy right now. Try again in a few seconds.", tone: "warning", remove: false, refresh: false };
  const message = e.message && !/^Request failed with status/.test(e.message) ? e.message : "Could not delete the game. Try again.";
  return { message, tone: "danger", remove: false, refresh: false };
}

/** One-line status for a saved game card. */
export function simGameLiteLine(game: Pick<SimGameLite, "status" | "current_week" | "grade_letter" | "settings">): string {
  if (game.status === "drafting") return "Draft in progress";
  if (game.status === "complete") return game.grade_letter ? `Finished · Grade ${game.grade_letter}` : "Finished";
  if (game.status === "playoffs") return `Playoffs · Week ${game.current_week}`;
  const total = game.settings.regular_weeks;
  return total ? `Week ${game.current_week} of ${total}` : `Week ${game.current_week}`;
}
