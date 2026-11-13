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

export type SimGameStatus = "drafting" | "in_season" | "playoffs" | "offseason" | "complete";
export type SimGamePhase = "draft" | "regular_season" | "playoffs" | "offseason" | "complete";
export type SimScoring = "ppr" | "half" | "std";
export type SimDifficulty = "easy" | "normal" | "hard";
export type SimTiebreaker = "points_for" | "head_to_head";
export const SIM_TIEBREAKER_LABELS: Record<SimTiebreaker, string> = { points_for: "Points for", head_to_head: "Head-to-head" };
export type SimPos = "QB" | "RB" | "WR" | "TE" | "K" | "DEF";
export type SimSlot = "QB" | "RB" | "WR" | "TE" | "FLEX" | "REC_FLEX" | "SUPER_FLEX" | "K" | "DEF";
/** League mode: redraft (one season) or dynasty (several seasons with an offseason, rookie draft and picks). */
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
  /** Coarse diagnostic code on sim_storage_unavailable (conflict, timeout, http_5xx, constraint, rls ...). */
  detail?: string;
  is_premium?: boolean;
  upsell?: SimGameUpsell | null;
  preview?: SimGamePreview | null;
  /** Small actions (claim, cancel, cut, lineup, trade, inbox) return the header slice they changed. */
  delta?: SimGameDelta;
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
  /** Age to a tenth when the server sends it; rows fall back to `age`. */
  age_decimal?: number | null;
  adp: number | null;
  /** Trade value on the sim's 0-100 scale (the best player is 100), not the main app's raw market value. Label it "Trade value", never "Value"/"VAL". */
  value: number;
  /**
   * Overall (1-99): where his value ranks among players at his position, the SAME definition and gauge as the main
   * app's OVR (modules/sim/game_view.overall_ratings). Null for a position pool too thin to rank, or an older server.
   */
  overall?: number | null;
  /** 1-based rank by model value across the whole pool (players list and player detail). */
  value_rank?: number | null;
  /** 1-based rank by model value among players at the same position (player detail only). */
  pos_value_rank?: number | null;
  /** ADP minus value rank (players list only): positive = the market lets him fall past the model (steal). */
  adp_edge?: number | null;
  /** Expected per-game points for the next game he can play, given his NFL team's depth chart and who is out. */
  projection: number;
  /** Per-game mean when healthy (the projection is 0.0 for an injured player this week). */
  ros_mean?: number | null;
  /** Team-level role (new games only): one fill-in per injured starter; the other backups show baseline numbers. */
  role?: SimPlayerRole | null;
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
  /** Dynasty / reserves engine (1.2.0); older saves omit these. */
  kind?: "player";
  /** Where the player sits: active roster, IR or the taxi squad. */
  squad?: SimSquad | null;
  taxi_eligible?: boolean;
  rookie?: boolean;
  /** True for a simulated (not real NFL draft) rookie. */
  generated?: boolean;
}

/** A player's role on his NFL team's depth chart in his next game (player-model-3 games; older saves omit it). */
export interface SimPlayerRole {
  kind: "starter" | "fill_in" | "backup" | "bench" | "out";
  /** "Starting while Hurts is out" / "Filling in for X" / "Backup"; null for a normal starter. */
  label: string | null;
  covering?: string | null;
  covering_name?: string | null;
  /** What he would average if he started (the old, role-free projection). */
  if_starts: number;
  week?: number | null;
}

/** The role chip for a row, or null when the player has the ordinary role. */
export function simRoleBadge(player: { role?: SimPlayerRole | null }): { label: string; tone: SimGameTone } | null {
  const role = player.role;
  if (!role || !role.label) return null;
  return { label: role.label, tone: role.kind === "fill_in" ? "accent" : "muted" };
}

/** Tags for a Players-list row: the owner, then the role chip (fill-in / backup). */
export function simPlayerTags(player: SimGamePlayer): { key: string; label: string; tone: SimGameTone }[] | undefined {
  const tags: { key: string; label: string; tone: SimGameTone }[] = [];
  if (player.owner) tags.push({ key: "owner", label: simOwnerLabel(player.owner), tone: simOwnerTone(player.owner) });
  const role = simRoleBadge(player);
  if (role) tags.push({ key: "role", label: role.label, tone: role.tone });
  return tags.length ? tags : undefined;
}

/** "If he starts: 13.5 pts" for a fill-in or backup: the separate hint next to the expected projection. */
export function simIfStartsHint(player: { role?: SimPlayerRole | null }): string | null {
  const role = player.role;
  if (!role || (role.kind !== "fill_in" && role.kind !== "backup")) return null;
  return `If he starts: ${simFmtPts(role.if_starts)} pts`;
}

/** Where one of your players sits. Picks report "picks". */
export type SimSquad = "roster" | "ir" | "taxi" | "picks";

/** A draft pick shaped like a player row (kind "pick"; the trade builder treats both as assets). */
export interface SimPickAsset extends Omit<SimGamePlayer, "pos" | "kind" | "squad" | "team"> {
  kind: "pick";
  pos: "PICK";
  team: string | null;
  squad?: "picks";
  /** "pick:<year>:<round>:<original team id>". */
  id: string;
  season: number;
  round: number;
  orig_team_id: string;
  orig_team_name: string;
  slot_hint: SimPickSlotHint | null;
  /** The engine's own name for the pick, e.g. "2027 Round 1 (early)". */
  label?: string;
  /** Set on GET /picks rows: true when the holder is also the original owner. */
  own?: boolean;
}

export type SimPickSlotHint = "early" | "mid" | "late";

/** A player or a pick: what a trade side holds. */
export type SimTradeAsset = SimGamePlayer | SimPickAsset;

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
  /** IR / taxi squads (saves from before game engine 1.2.0 omit all of these). */
  reserve_v?: number;
  ir_slots?: number;
  taxi_slots?: number;
  taxi_years?: number;
  /** Dynasty only. */
  seasons?: number;
  start_year?: number;
  pick_years?: number;
  rookie_rounds?: number;
  dynasty_v?: number;
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
  /** Dynasty games only (null or absent otherwise). */
  dynasty?: SimDynastyBlock | null;
  grade_letter: string | null;
  created_at: string;
  updated_at: string;
}

/** The slice of `SimGame` a small action can change, returned with the action's own response so the
 *  header updates without refetching the whole game (see `simApplyDelta`). */
export interface SimGameDelta {
  status: SimGameStatus;
  week: number;
  pending: SimGamePending;
  can_trade: boolean;
}

/** How long after an action's delta the screen skips its own full reload, and how long it then waits to confirm in the background. */
export const SIM_DELTA_FRESH_MS = 2000;
export const SIM_RECONCILE_MS = 1500;

/** `game` with an action's delta applied. A delta from a different week or phase (the game moved on
 *  underneath) is ignored: that case needs the full reload. Returns the same object when nothing changed. */
export function simApplyDelta(game: SimGame, delta: SimGameDelta | null | undefined): SimGame {
  if (!delta || delta.week !== game.week || delta.status !== game.status) return game;
  const same = game.can_trade === delta.can_trade && JSON.stringify(game.pending) === JSON.stringify(delta.pending);
  return same ? game : { ...game, pending: delta.pending, can_trade: delta.can_trade };
}

/** `items` without the one with `id` (optimistic cancel / decline); same array when it is not there. */
export function simWithout<T extends { id: string }>(items: readonly T[], id: string): T[] {
  return items.some((i) => i.id === id) ? items.filter((i) => i.id !== id) : (items as T[]);
}

/** A claim shown the instant the user taps Queue; the server's list replaces it when the call returns. */
export function simOptimisticClaim(add: SimGamePlayer, drop: SimGamePlayer | null, startSlot: SimSlot | null): SimWaiverClaim {
  return { id: `pending-${add.id}`, add, drop, start_slot: startSlot };
}

/** The small dynasty block every game payload carries. */
export interface SimDynastyBlock {
  season_no: number;
  seasons: number;
  year: number;
  /** "review" | "rookie_draft" | "cutdown" during the offseason, else null. */
  stage: SimOffseasonStage | null;
  picks_held: number;
  titles: number;
  /** True while playing the final season. */
  last_season: boolean;
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
    ir_slots?: { min: number; max: number; default: number };
    taxi_slots?: { min: number; max: number; default: number; default_dynasty?: number };
    taxi_years?: { values: number[]; default: number };
    /** Dynasty only. */
    seasons?: { values: number[]; default: number };
    rookie_rounds?: { values: number[]; default: number };
  };
  dynasty?: { pick_years: number; max_seasons: number; start_year: number };
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
  /** Dynasty: 3, 4 or 5 seasons (the cap). */
  seasons?: number;
  rookie_rounds?: number;
  ir_slots?: number;
  taxi_slots?: number;
  taxi_years?: number;
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

/** Rest-of-season line of a player detail: per-game mean and band, remaining weeks, bye and out weeks. */
export interface SimRosSummary {
  mean: number;
  floor: number;
  ceiling: number;
  weeks_left: number;
  playable_weeks: number;
  bye_week: number | null;
  out_weeks: number[];
}

/** Generated-prospect scouting profile (player detail of a generated rookie). Shaped so real college stats can slot in unchanged:
 * fill `college.seasons[].stats` for the keys named in `college.columns` and set `source` to something other than "generated". */
export interface SimScoutingTag {
  tag: string;
  confidence: number;
}

export interface SimScoutingMeasurable {
  key: string;
  label: string;
  display: string;
  percentile: number;
}

export interface SimScoutingAnalytic {
  key: string;
  label: string;
  value: number;
  display: string;
  percentile: number;
  higher_is_better: boolean;
}

export interface SimScoutingCollegeColumn {
  key: string;
  label: string;
  fmt: "int" | "num1" | "num2" | "pct1";
}

export interface SimScoutingCollege {
  columns: SimScoutingCollegeColumn[];
  seasons: { season: number; team: string; class: string; games: number; stats: Record<string, number> }[];
  career: Record<string, number>;
  /** Percentile vs the position class for the final season's stats, by column key. */
  percentiles: Record<string, number>;
  final: { season: number; team: string; games: number; stats: Record<string, number> };
}

export interface SimDevelopmentPoint {
  year: number;
  mean: number;
  lo: number;
  hi: number;
}

export interface SimDevelopmentCurve {
  base_year: number;
  points: SimDevelopmentPoint[];
  confidence: number;
  confidence_label: "Low" | "Medium" | "High";
  /** Only set once scouts have a firm read (confidence 0.75+); until then just the vague tags. */
  archetype: string | null;
  archetype_label: string | null;
  revealed: boolean;
  note: string;
}

export interface SimScoutingProfile {
  version: number;
  source: string;
  label: string;
  school: string;
  class_year: number | null;
  position_word: string;
  draft: { round: number; pick: number; class_rank: number; class_size: number; basis: string };
  measurables: SimScoutingMeasurable[];
  college: SimScoutingCollege;
  analytics: SimScoutingAnalytic[];
  tags: SimScoutingTag[];
  blurb: string;
  development: SimDevelopmentCurve;
}

export interface SimPlayerDetailResponse extends SimGameEnvelope {
  /** Present for generated rookies only. */
  scouting?: SimScoutingProfile;
  player?: SimGamePlayer;
  weeks?: SimPlayerWeek[];
  /** True when every playable week carries the same projection (render one summary, never a week-by-week list). */
  projection_flat?: boolean;
  ros?: SimRosSummary;
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
  /** IR and taxi squads (empty and no `reserves` on saves from before them). */
  ir?: SimGamePlayer[];
  taxi?: SimGamePlayer[];
  reserves?: SimReserves;
  /** Present on POST /roster/move. */
  move?: { pid: string; src: string; dst: string };
}

export interface SimReserves {
  enabled: boolean;
  ir_slots: number;
  taxi_slots: number;
  taxi_years: number;
  ir_used: number;
  taxi_used: number;
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
  /** Scouting detail (GET /teams/{id}); absent on the plain roster payloads. */
  team?: SimTeamProfile;
  lineup?: SimLineupSlot[];
  projected_total?: number;
  positions?: SimPositionGrade[];
  strengths?: SimPos[];
  needs?: SimPos[];
  injuries?: SimGamePlayer[];
  recent?: SimTeamMove[];
  next_game?: { week: number; opponent: SimTeamRef } | null;
  trade?: { open: boolean; reason: string | null };
  ir?: SimGamePlayer[];
  taxi?: SimGamePlayer[];
  reserves?: SimReserves;
}

// ---------------------------------------------------------------------------
// Trades and inbox

export type SimTradeDecision = "accept" | "counter" | "decline";

export interface SimTradeVerdict {
  decision: SimTradeDecision;
  reason_code?: string;
  reason: string;
  chips?: string[];
  counter?: { give: SimTradeAsset[]; get: SimTradeAsset[] } | null;
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
  you_give: SimTradeAsset[];
  you_get: SimTradeAsset[];
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
  /** Dynasty games: grade and review are null; the multi-year summary is here. */
  mode?: SimMode;
  dynasty?: SimDynastySummary | null;
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
  ir_full: "Your IR is full.",
  ir_ineligible: "Only an injured (out) player on your active roster can go on IR.",
  taxi_full: "Your taxi squad is full.",
  taxi_ineligible: "Only rookies and young players can go on the taxi squad.",
  roster_full: "Your roster is full. Cut someone first.",
  reserves_unavailable: "This game has no IR or taxi squad.",
  not_dynasty: "That is only in dynasty games.",
  pool_exhausted: "No rookies are left to draft.",
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

/** A failed ACTION (pick, claim, trade) that is worth one automatic retry: storage hiccup or busy server, never "feature off". */
export function simIsTransientGate(gate: SimGameGate | null): boolean {
  return gate !== null && gate.kind === "unavailable" && gate.cause !== "off";
}

/** Inline copy for a failed action. The game stays on screen: only the initial load shows the full-page unavailable state. */
export function simActionFailureMessage(body?: SimGameEnvelope | null, gate?: SimGameGate | null): string {
  if (gate && gate.kind === "unavailable" && gate.cause === "busy") return "The simulator is busy right now. Try again in a few seconds.";
  const code = body?.detail ? ` (${body.detail})` : "";
  return `Couldn't save that. Your game is safe. Try it again${code}.`;
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

export type SimGameStage = "draft" | "week" | "playoffs" | "offseason" | "final";

export function simGameStage(game: Pick<SimGame, "status">): SimGameStage {
  switch (game.status) {
    case "drafting":
      return "draft";
    case "playoffs":
      return "playoffs";
    case "offseason":
      return "offseason";
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
  if (game.phase === "offseason") return "Offseason";
  return `Advance to week ${game.week + 1}`;
}

// ---------------------------------------------------------------------------
// Draft helpers

export const SIM_QUEUE_MAX = 30;
export const SIM_POSITIONS: SimPos[] = ["QB", "RB", "WR", "TE", "K", "DEF"];

/** A position filter value: a real position or a flex eligibility group (server: game_view.players_page). */
export type SimPosFilter = SimPos | "FLEX" | "SUPER_FLEX";
/** Positions a flex filter covers, from the game's lineup slot definitions (modules/sim/types.py FLEX_SLOTS). */
export const SIM_FLEX_GROUPS: Record<"FLEX" | "SUPER_FLEX", SimPos[]> = { FLEX: ["RB", "WR", "TE"], SUPER_FLEX: ["QB", "RB", "WR", "TE"] };

/**
 * Pills for a player-list position filter, in order QB RB WR TE FLEX SUPER_FLEX K DEF.
 * FLEX shows when the league has a FLEX, REC_FLEX or SUPER_FLEX slot, SUPER_FLEX
 * only with a super-flex slot, K / DEF only when a slot uses them.
 */
export function simFilterPositionsFor(slots: SimSlot[] | undefined): { label: string; value: SimPosFilter }[] {
  const list = slots ?? [];
  const has = (s: SimSlot) => list.includes(s);
  const out: { label: string; value: SimPosFilter }[] = (["QB", "RB", "WR", "TE"] as SimPos[]).map((p) => ({ label: p, value: p }));
  if (has("FLEX") || has("REC_FLEX") || has("SUPER_FLEX")) out.push({ label: "FLEX", value: "FLEX" });
  if (has("SUPER_FLEX")) out.push({ label: "SUPERFLEX", value: "SUPER_FLEX" });
  if (has("K")) out.push({ label: "K", value: "K" });
  if (has("DEF")) out.push({ label: "DEF", value: "DEF" });
  return out;
}

/** Does a player's position pass a position filter value (client-side twin of the server rule)? */
export function simPosMatches(pos: SimPos, filter: SimPosFilter | ""): boolean {
  if (!filter) return true;
  if (filter === "FLEX" || filter === "SUPER_FLEX") return SIM_FLEX_GROUPS[filter].includes(pos);
  return pos === filter;
}

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
  pos: SimPosFilter | "";
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
  | { type: "pos"; value: SimPosFilter | "" }
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
/** A dynasty trade side holds up to 4 assets (players and picks). */
export const SIM_TRADE_MAX_PER_SIDE_DYNASTY = 4;

export function simTradeMaxPerSide(settings: Pick<SimGameSettings, "mode"> | null | undefined): number {
  return settings?.mode === "dynasty" ? SIM_TRADE_MAX_PER_SIDE_DYNASTY : SIM_TRADE_MAX_PER_SIDE;
}

export interface SimTradeDraft {
  partner: string | null;
  give: string[];
  get: string[];
}

export type SimTradeAction =
  | { type: "partner"; teamId: string | null }
  | { type: "toggle"; side: "give" | "get"; id: string; max?: number }
  | { type: "set"; side: "give" | "get"; ids: string[]; max?: number }
  | { type: "load"; give: string[]; get: string[]; max?: number }
  | { type: "seed"; seed: SimTradeSeed; max?: number }
  | { type: "clear" };

/** A player handed to the trade builder from elsewhere (quick view, Players tab, team sheet). `partner` "" keeps the current partner. */
export interface SimTradeSeed {
  partner: string;
  give?: string;
  get?: string;
}

/**
 * The one rule for "Add to trade": my player goes on the give side (partner unchanged), an AI
 * team's player picks that team as the partner and goes on the get side. Free agents cannot be
 * traded, so they yield null.
 */
export function simTradeSeedFor(player: Pick<SimGamePlayer, "id" | "owner">): SimTradeSeed | null {
  const owner = player.owner;
  if (!owner || owner.type === "free_agent") return null;
  if (owner.type === "you") return { partner: "", give: player.id };
  return owner.team_id ? { partner: owner.team_id, get: player.id } : null;
}

/** Apply a seed to a draft. Idempotent: adding a player already in the offer leaves it there. */
export function simApplyTradeSeed(draft: SimTradeDraft, seed: SimTradeSeed, max: number = SIM_TRADE_MAX_PER_SIDE): SimTradeDraft {
  let next = seed.partner && seed.partner !== draft.partner ? { partner: seed.partner, give: draft.give, get: [] as string[] } : draft;
  if (seed.give && !next.give.includes(seed.give) && next.give.length < max) next = { ...next, give: [...next.give, seed.give] };
  if (seed.get && !next.get.includes(seed.get) && next.get.length < max) next = { ...next, get: [...next.get, seed.get] };
  return next;
}

export const SIM_TRADE_EMPTY: SimTradeDraft = { partner: null, give: [], get: [] };

/** Trade builder reducer: switching partner clears the incoming side; sides cap at 3. */
export function simTradeReducer(state: SimTradeDraft, action: SimTradeAction): SimTradeDraft {
  switch (action.type) {
    case "partner":
      return state.partner === action.teamId ? state : { partner: action.teamId, give: state.give, get: [] };
    case "toggle": {
      const list = state[action.side];
      if (list.includes(action.id)) return { ...state, [action.side]: list.filter((id) => id !== action.id) };
      if (list.length >= (action.max ?? SIM_TRADE_MAX_PER_SIDE)) return state;
      return { ...state, [action.side]: [...list, action.id] };
    }
    case "set":
      return { ...state, [action.side]: [...new Set(action.ids)].slice(0, action.max ?? SIM_TRADE_MAX_PER_SIDE) };
    case "load":
      return { ...state, give: action.give.slice(0, action.max ?? SIM_TRADE_MAX_PER_SIDE), get: action.get.slice(0, action.max ?? SIM_TRADE_MAX_PER_SIDE) };
    case "seed":
      return simApplyTradeSeed(state, action.seed, action.max);
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
  if (age) parts.push(`${age}y`);
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
  if (game.phase === "offseason") return "Offseason";
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
  /** Redraft (one season) or dynasty (several, with an offseason). */
  mode: SimMode;
  /** Dynasty: how many seasons (the cap). */
  seasons: number;
  /** Dynasty: rounds in each rookie draft. */
  rookieRounds: number;
  /** IR / taxi: null means "the engine default" (or the league's own on a league import) and is not sent. */
  irSlots: number | null;
  taxiSlots: number | null;
  taxiYears: number | null;
}

/** Dynasty setup fallbacks, used until the options response says otherwise. */
export const SIM_DYNASTY_FALLBACK = { seasons: 5, rookieRounds: 4, irSlots: 2, taxiSlots: 0, taxiSlotsDynasty: 4, taxiYears: 2 };

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
    mode: o?.mode?.default ?? "redraft",
    seasons: o?.seasons?.default ?? SIM_DYNASTY_FALLBACK.seasons,
    rookieRounds: o?.rookie_rounds?.default ?? SIM_DYNASTY_FALLBACK.rookieRounds,
    irSlots: null,
    taxiSlots: null,
    taxiYears: null,
  };
}

/** True when any "Advanced options" field differs from its default (so a collapsed section can say so). */
export function simSetupAdvancedChanged(state: SimSetupState, defaults: SimSetupState): number {
  const keys: (keyof SimSetupState)[] = [
    "scoring", "tePremium", "superflex", "includeK", "includeDef", "tiebreaker", "bench", "teams",
    "mode", "seasons", "rookieRounds", "irSlots", "taxiSlots", "taxiYears",
  ];
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
  const dynasty = state.mode === "dynasty";
  const reserves: SimGameCreateBody = {
    ...(state.irSlots != null ? { ir_slots: state.irSlots } : {}),
    ...(state.taxiSlots != null ? { taxi_slots: state.taxiSlots } : {}),
    ...(state.taxiYears != null ? { taxi_years: state.taxiYears } : {}),
  };
  if (state.start === "league") {
    return {
      ...common,
      start: "league",
      league_id: state.leagueId,
      ...(state.rosterId ? { roster_id: state.rosterId } : {}),
      ...(dynasty ? { mode: "dynasty" as const, seasons: state.seasons, rookie_rounds: state.rookieRounds } : {}),
      ...reserves,
    };
  }
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
    mode: dynasty ? "dynasty" : "redraft",
    ...(dynasty ? { seasons: state.seasons, rookie_rounds: state.rookieRounds } : {}),
    ...reserves,
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
  if (settings.mode === "dynasty") parts.unshift(settings.seasons ? `Dynasty (${settings.seasons} seasons)` : "Dynasty");
  if (settings.start === "league") parts.push("From your league");
  return parts.join(" · ");
}

/** What the setup tells the player about the league they are about to start. */
export function simSetupSummary(state: SimSetupState, layoutHint?: SimGameOptionsResponse["layout"]): string {
  const dynasty = state.mode === "dynasty";
  if (state.start === "league") {
    const base = "Your league's size, lineup, scoring and current rosters. A new 14-week season; nothing changes in your real league.";
    return dynasty ? `${base} ${simDynastyLine(state.seasons, state.rookieRounds)}` : base;
  }
  const layout = simDeriveLayout(state, layoutHint?.base_slots, layoutHint?.draft_spare_spots);
  const base = `${state.teams} teams, ${layout.rounds}-round snake draft. Starters: ${layout.slots.join(", ")}. Roster ${layout.rosterLimit}.`;
  return dynasty ? `${base} ${simDynastyLine(state.seasons, state.rookieRounds)}` : base;
}

/** "Dynasty: 5 seasons, a 4-round rookie draft each offseason." */
export function simDynastyLine(seasons: number, rookieRounds: number): string {
  return `Dynasty: up to ${seasons} seasons, with a ${rookieRounds}-round rookie draft each offseason.`;
}

/** Plain note under the mode choice when a real league is imported as dynasty. */
export function simSetupDynastyNote(state: Pick<SimSetupState, "start" | "mode">): string | null {
  if (state.mode !== "dynasty") return null;
  const base =
    state.start === "league"
      ? "Starting from your league as dynasty brings its traded picks, taxi squad and IR along."
      : "Dynasty keeps your team going for several seasons. After each one: aging, retirements, a rookie draft and roster cuts.";
  return `${base} ${SIM_SETUP_ROOKIE_CLASS_NOTE}`;
}

/** One plain sentence for the dynasty setup: the rookie classes are not the real NFL draft. */
export const SIM_SETUP_ROOKIE_CLASS_NOTE = "Incoming rookie classes are simulated, with generated names and talent.";

/** The disclosure shown the first time a rookie draft opens and behind every "Generated class" info tap. */
export const SIM_GENERATED_CLASS_NOTICE =
  "These rookies are simulated, not the real NFL draft class. Names and talent are generated for the game.";

/** Short chip label for a generated rookie class. */
export const SIM_GENERATED_CLASS_LABEL = "Generated class";

/** "Generated class" or "Generated class - strong" when the strength is known. */
export function simGeneratedClassLabel(strength?: SimRookieClassStrength | string | null): string {
  return strength === "weak" || strength === "average" || strength === "strong" ? `${SIM_GENERATED_CLASS_LABEL} - ${strength}` : SIM_GENERATED_CLASS_LABEL;
}

/** The chip label for an offseason payload, or null when the class is not generated (older saves). */
export function simRookieClassChip(off: Pick<SimOffseason, "rookie_class"> | null | undefined): string | null {
  const rc = off?.rookie_class;
  return rc && rc.generated ? simGeneratedClassLabel(rc.strength) : null;
}

/** True for a rookie row that is simulated (draws the small per-row chip). */
export function simPlayerIsGenerated(player: Pick<SimGamePlayer, "generated">): boolean {
  return player.generated === true;
}

/** Storage key for "this game's generated-class popup was dismissed". */
export function simRookieNoticeKey(gameId: string): string {
  return `fgl:sim-rookie-notice:${gameId}`;
}

/** Mode choices the options say are playable ("Redraft" and, when available, "Dynasty"). */
export function simSetupModes(options: SimGameOptionsResponse | null | undefined): { value: SimMode; label: string }[] {
  const modes = options?.options?.mode;
  const labels: Record<SimMode, string> = { redraft: "Redraft", dynasty: "Dynasty" };
  const values = modes?.values ?? ["redraft"];
  return values.map((value) => ({ value, label: labels[value] ?? value }));
}

/** The engine default for taxi slots in this mode (0 in redraft, 4 in dynasty by default). */
export function simSetupTaxiDefault(options: SimGameOptionsResponse | null | undefined, mode: SimMode): number {
  const t = options?.options?.taxi_slots;
  if (mode === "dynasty") return t?.default_dynasty ?? SIM_DYNASTY_FALLBACK.taxiSlotsDynasty;
  return t?.default ?? SIM_DYNASTY_FALLBACK.taxiSlots;
}

/** Pill options for a "Default or 0..max" count (null = the default, labelled with its value when known). */
export function simSetupCountOptions(max: number, defaultValue: number | null, min = 0): { label: string; value: string }[] {
  const out = [{ label: defaultValue == null ? "Default" : `Default (${defaultValue})`, value: "" }];
  for (let n = min; n <= max; n += 1) out.push({ label: String(n), value: String(n) });
  return out;
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

// ---------------------------------------------------------------------------
// Home dashboard and team scouting (GET /home, GET /teams/{id})

export interface SimTeamRef {
  team_id: string;
  name: string;
  persona_id?: string;
  is_you?: boolean;
}

export interface SimTeamRecord {
  wins: number;
  losses: number;
  ties: number;
  pf: number;
  pa: number;
  rank: number;
  streak?: string;
  seed?: number | null;
  playoff_status?: string;
}

export interface SimTeamProfile {
  team_id: string;
  name: string;
  owner?: string;
  is_you: boolean;
  persona: SimGamePersona;
  record: SimTeamRecord | null;
  power_rank: number;
  avg_age: number | null;
  roster_size: number;
}

/** One team in GET /league/rosters: the League tab's who-has-who row and the trade partner card. */
export interface SimLeagueRosterTeam extends SimTeamProfile {
  positions: SimPositionGrade[];
  strengths: SimPos[];
  needs: SimPos[];
  /** Positions with spare depth to trade from (two or more players beyond the starters). */
  surplus: SimPos[];
  /** Highest-value players held (roster, IR and taxi). */
  top_assets: SimGamePlayer[];
  /** Everyone the team holds, by value; `squad` says roster, ir or taxi. */
  players: SimGamePlayer[];
}

export interface SimLeagueRostersResponse extends SimGameEnvelope {
  teams?: SimLeagueRosterTeam[];
  week?: number;
}

export type SimNeedLevel = "strength" | "ok" | "need";

export interface SimPositionGrade {
  pos: SimPos;
  rank: number;
  teams: number;
  level: SimNeedLevel;
  depth: number;
  starters: number;
  strength: number;
}

export interface SimTeamMove {
  week: number;
  type: string;
  text: string;
  players: SimTransactionPlayer[];
}

export interface SimHomeMatchupRow {
  slot: SimSlot;
  you: SimGamePlayer | null;
  opp: SimGamePlayer | null;
}

export interface SimHomeMatchup {
  week: number;
  bye: boolean;
  kind: "regular" | "playoff";
  opponent: (SimTeamRef & { record: SimTeamRecord | null; persona: SimGamePersona }) | null;
  you_record?: SimTeamRecord | null;
  you_projection?: number;
  opp_projection?: number;
  /** Chance (0 to 1) you outscore the opponent, from the projection spread. */
  win_prob?: number;
  rows: SimHomeMatchupRow[];
  you_flagged?: number;
  opp_flagged?: number;
}

export type SimChecklistSeverity = "danger" | "warning" | "accent" | "ok";
export type SimTabTarget = "home" | "team" | "players" | "trades" | "league" | "more";

export interface SimChecklistItem {
  id: "cuts" | "lineup" | "waivers" | "byes" | "offers" | string;
  label: string;
  detail: string;
  done: boolean;
  target: SimTabTarget;
  severity: SimChecklistSeverity;
}

export interface SimHomeOffer {
  id: string;
  from: SimTeamRef;
  you_give: SimGamePlayer[];
  you_get: SimGamePlayer[];
  expires_week: number;
}

export interface SimWaiverSuggestion {
  player: SimGamePlayer;
  gain_now: number;
  gain_ros: number;
  reasons: string[];
  drop: SimGamePlayer | null;
  covers: SimGamePlayer | null;
  for_slot: string | null;
}

export interface SimByeAlert {
  week: number;
  weeks_away: number;
  slot: SimSlot;
  /** Your rank at the position, e.g. "WR1". */
  pos_label: string;
  player: SimGamePlayer;
  covered: boolean;
  covered_by: SimGamePlayer | null;
  replacements: SimGamePlayer[];
  message: string;
}

export interface SimHomeInjury {
  player: SimGamePlayer;
  out_weeks: number;
  starting: boolean;
  note: string;
}

export interface SimTrendRow {
  player: SimGamePlayer;
  last_week: number;
  /** Last week's points minus the player's preseason projection. */
  delta: number;
  avg: number;
}

export interface SimHomeStandings {
  rows: SimStandingRow[];
  playoff_spots: number;
  games_left: number;
  your_rank: number | null;
  /** Wins ahead of (positive) or behind (negative) the playoff cut line. */
  margin: number | null;
  in_playoffs: boolean;
}

export interface SimHomeSpotlight {
  week: number;
  text: string;
  headline: string;
  team_a: SimTeamRef;
  team_b: SimTeamRef;
  players: SimTransactionPlayer[];
}

export interface SimHomeResponse extends SimGameEnvelope {
  week?: number;
  phase?: "regular_season" | "playoffs";
  matchup?: SimHomeMatchup | null;
  checklist?: SimChecklistItem[];
  inbox?: { count: number; open: boolean; items: SimHomeOffer[] };
  waiver_suggestions?: SimWaiverSuggestion[];
  bye_alerts?: SimByeAlert[];
  injuries?: SimHomeInjury[];
  hot_cold?: { hot: SimTrendRow[]; cold: SimTrendRow[]; wire: SimTrendRow[] };
  standings?: SimHomeStandings;
  league?: { recent: (SimTransaction & { team_id: string; text: string })[]; spotlight: SimHomeSpotlight | null };
  /** IR / taxi usage (reserve games only). */
  reserves?: { ir_used: number; ir_slots: number; taxi_used: number; taxi_slots: number };
  /** Dynasty games only: where you are and what you hold. `next_pick` is a pick id "season:round:team". */
  dynasty?: { season_no: number; seasons: number; picks_held: number; picks_value: number; next_pick: string | null };
  /** Cards the server could not build (card name to error class); the rest of the page is valid. */
  errors?: Record<string, string>;
}

/** One plain line for the Home dynasty/IR strip, or null when the game has neither. */
export function simHomeDynastyLine(home: Pick<SimHomeResponse, "reserves" | "dynasty"> | null | undefined): string | null {
  if (!home) return null;
  const parts: string[] = [];
  if (home.dynasty) {
    parts.push(`Season ${home.dynasty.season_no} of ${home.dynasty.seasons}`);
    parts.push(`${home.dynasty.picks_held} pick${home.dynasty.picks_held === 1 ? "" : "s"}`);
  }
  if (home.reserves) {
    if (home.reserves.ir_slots > 0) parts.push(`IR ${home.reserves.ir_used}/${home.reserves.ir_slots}`);
    if (home.reserves.taxi_slots > 0) parts.push(`Taxi ${home.reserves.taxi_used}/${home.reserves.taxi_slots}`);
  }
  return parts.length ? parts.join(" · ") : null;
}

/** Section glyph names shared by web (inline SVG) and the app (Ionicons map). */
export type SimGlyphName =
  | "matchup"
  | "checklist"
  | "waiver"
  | "bye"
  | "injury"
  | "trade"
  | "standings"
  | "hot"
  | "cold"
  | "league"
  | "team"
  | "check"
  | "alert"
  | "spark";

export function simWinChanceLabel(prob: number | null | undefined): string {
  if (prob == null || Number.isNaN(prob)) return "-";
  const pct = Math.round(prob * 100);
  return `${Math.min(99, Math.max(1, pct))}%`;
}

export function simWinChanceTone(prob: number | null | undefined): SimGameTone {
  if (prob == null) return "muted";
  if (prob >= 0.55) return "success";
  if (prob <= 0.45) return "danger";
  return "warning";
}

/** Green up / red down trend text, e.g. "+6.1" with a matching arrow. */
export function simTrendText(delta: number | null | undefined): { text: string; arrow: string; tone: SimGameTone } {
  if (delta == null || Math.abs(delta) < 0.05) return { text: "0.0", arrow: "", tone: "muted" };
  const up = delta > 0;
  return { text: `${up ? "+" : "-"}${Math.abs(delta).toFixed(1)}`, arrow: up ? "\u25B2" : "\u25BC", tone: up ? "success" : "danger" };
}

export function simChecklistTone(severity: SimChecklistSeverity): SimGameTone {
  if (severity === "ok") return "success";
  // Newer engines may add severities: show them as a plain to-do instead of an unstyled row.
  return severity === "danger" || severity === "warning" || severity === "accent" ? severity : "warning";
}

const CHECKLIST_TARGETS: readonly string[] = ["home", "team", "players", "trades", "league", "more"];

/** The tab a checklist row opens, or null for a target this build does not know (the row is then not a link). */
export function simChecklistTarget(item: Pick<SimChecklistItem, "target">): SimTabTarget | null {
  return CHECKLIST_TARGETS.includes(item.target) ? item.target : null;
}

export function simChecklistProgress(items: Pick<SimChecklistItem, "done">[] | undefined): { done: number; total: number } {
  const list = items ?? [];
  return { done: list.filter((i) => i.done).length, total: list.length };
}

export function simLevelTone(level: SimNeedLevel): SimGameTone {
  return level === "strength" ? "success" : level === "need" ? "danger" : "muted";
}

export function simLevelLabel(level: SimNeedLevel): string {
  return level === "strength" ? "Strength" : level === "need" ? "Need" : "Solid";
}

/** "Strong at RB, WR. Needs TE." (empty when nothing stands out). */
export function simStrengthNeedLine(strengths: string[] | undefined, needs: string[] | undefined): string {
  const parts: string[] = [];
  if (strengths?.length) parts.push(`Strong at ${strengths.join(", ")}.`);
  if (needs?.length) parts.push(`Needs ${needs.join(", ")}.`);
  return parts.join(" ");
}

/** Which side a matchup row favors by projection ("even" within a point). */
export function simRowEdge(row: Pick<SimHomeMatchupRow, "you" | "opp">): "you" | "opp" | "even" {
  const diff = (row.you?.projection ?? 0) - (row.opp?.projection ?? 0);
  return Math.abs(diff) < 1 ? "even" : diff > 0 ? "you" : "opp";
}

/** Projection gap to show between a pair of slot players, signed from your side. */
export function simRowGap(row: Pick<SimHomeMatchupRow, "you" | "opp">): number {
  return Math.round(((row.you?.projection ?? 0) - (row.opp?.projection ?? 0)) * 10) / 10;
}

/** The standings rows around you (and always the playoff line), trimmed to `size`. */
export function simStandingsWindow(rows: SimStandingRow[], size = 6): SimStandingRow[] {
  if (rows.length <= size) return rows;
  const at = Math.max(0, rows.findIndex((r) => r.is_you));
  let start = Math.max(0, at - Math.floor(size / 2));
  start = Math.min(start, rows.length - size);
  return rows.slice(start, start + size);
}

export function simMarginLine(standings: Pick<SimHomeStandings, "margin" | "in_playoffs" | "playoff_spots" | "games_left"> | undefined): string {
  if (!standings || standings.margin == null) return "";
  const m = standings.margin;
  const wins = (n: number) => `${Math.abs(n) === 1 ? "1 win" : `${Math.abs(n)} wins`}`;
  const left = standings.games_left === 1 ? "1 game left" : `${standings.games_left} games left`;
  if (m === 0) return `Right on the cut line with ${left}.`;
  return m > 0
    ? `${wins(m)} clear of the cut line, ${left}.`
    : `${wins(m)} behind the cut line, ${left}.`;
}

/** Record line for a team ref with a record, "5-2". */
export function simTeamRecordLine(record: Pick<SimTeamRecord, "wins" | "losses" | "ties"> | null | undefined): string {
  return record ? simFmtRecord(record) : "";
}

/** Bye-week cover line for a dashboard row. */
export function simByeCoverLine(alert: Pick<SimByeAlert, "week" | "covered" | "pos_label">): string {
  return alert.covered ? `${alert.pos_label} covered in Week ${alert.week}` : `${alert.pos_label} needs a fill-in for Week ${alert.week}`;
}

/**
 * Fallback display name for tight phone layouts: "Elijah Stone Jr." becomes
 * "E. Stone Jr." only when the full name is long; short names are kept whole.
 */
export function simShortName(name: string, maxLength = 17): string {
  const words = name.trim().split(/\s+/).filter(Boolean);
  if (name.length <= maxLength || words.length < 2) return name;
  const suffix = /^(jr\.?|sr\.?|ii|iii|iv|v)$/i.test(words[words.length - 1]) && words.length > 2 ? ` ${words[words.length - 1]}` : "";
  const last = suffix ? words[words.length - 2] : words[words.length - 1];
  return `${words[0][0]}. ${last}${suffix}`;
}

// ---------------------------------------------------------------------------
// Dynasty: picks, offseason, rookie draft, summary (game engine 1.2.0)

/** Endpoint paths for the dynasty and reserve routes (web and mobile call these through their own fetch). */
export function simDynastyPaths(gameId: string) {
  const base = `/v1/sim/games/${encodeURIComponent(gameId)}`;
  return {
    picks: `${base}/picks`,
    rosterMove: `${base}/roster/move`,
    offseason: (pos?: string) => `${base}/offseason${pos ? `?pos=${encodeURIComponent(pos)}` : ""}`,
    rookieDraftStart: `${base}/offseason/rookie-draft/start`,
    rookieDraftPick: `${base}/offseason/rookie-draft/pick`,
    rookieDraftAuto: `${base}/offseason/rookie-draft/auto`,
    startSeason: `${base}/offseason/start-season`,
    dynasty: `${base}/dynasty`,
  };
}

export type SimRookieClassStrength = "weak" | "average" | "strong";

export interface SimRookieClass {
  generated: boolean;
  strength: SimRookieClassStrength;
  size?: number;
}

export type SimOffseasonStage = "review" | "rookie_draft" | "cutdown";

export interface SimPicksTeam {
  team_id: string;
  name: string;
  is_you: boolean;
  picks: SimPickAsset[];
  total_value: number;
}

/** GET /games/{id}/picks (reason "not_dynasty" on a redraft game). */
export interface SimPicksResponse extends SimGameEnvelope {
  enabled?: boolean;
  draft_year?: number;
  rounds?: number;
  years?: number;
  you?: SimPickAsset[];
  teams?: SimPicksTeam[];
}

export interface SimTopScorer {
  id: string;
  name: string;
  pos: string;
  pts: number;
}

export interface SimSeasonArchiveYou {
  rank: number;
  wins: number;
  losses: number;
  ties: number;
  pf: number;
  pa?: number;
  seed?: number | null;
  playoff_result: string;
  made_playoffs: boolean;
  avg_age: number | null;
  top_scorers: SimTopScorer[];
}

export interface SimSeasonChampion {
  team_id: string;
  name: string;
  is_you: boolean;
}

/** One finished season, as stored in the dynasty archive (offseason.last_season). */
export interface SimSeasonArchive {
  season_no: number;
  year: number;
  champion: SimSeasonChampion | null;
  you: SimSeasonArchiveYou;
  standings?: { rank: number; team_id: string; name: string; is_you: boolean; wins: number; losses: number; ties: number; pf: number; playoff_result: string }[];
}

export interface SimOffseasonRetiree {
  id: string;
  name: string;
  pos: string;
  age: number | null;
  market?: number | null;
  is_yours: boolean;
}

/** A player of yours with last season's and this season's age and expected points. */
export interface SimOffseasonMover extends SimGamePlayer {
  age_before: number | null;
  age_after: number | null;
  mean_before: number;
  mean_after: number;
  delta: number;
}

export interface SimRookieOrderRow {
  n: number;
  round: number;
  pick: string;
  orig_team_id: string;
  orig_team_name: string;
  team_id: string | null;
  team_name: string | null;
  is_yours: boolean;
  traded: boolean;
  made: { id: string; name: string; pos: string } | null;
}

export interface SimOffseasonRoster {
  size: number;
  limit: number;
  cuts_needed: number;
  ir: SimGamePlayer[];
  taxi: SimGamePlayer[];
  reserves: SimReserves;
}

export type SimOffseasonNextAction = "start_rookie_draft" | "finish_draft" | "start_season";

export interface SimOffseason {
  stage: SimOffseasonStage;
  /** Calendar year of the coming season. */
  year: number;
  /** The season just finished (the next one is season_no + 1). */
  season_no: number;
  seasons: number;
  next_year?: number;
  last_season: SimSeasonArchive | null;
  retired: SimOffseasonRetiree[];
  movers: SimOffseasonMover[];
  your_picks_this_draft: SimRookieOrderRow[];
  draft: {
    round_count: number;
    total: number;
    pick_index: number;
    order: SimRookieOrderRow[];
    on_clock: SimRookieOrderRow | null;
    your_turn: boolean;
    available: SimGamePlayer[];
    available_count: number;
  };
  roster: SimOffseasonRoster;
  can_trade: boolean;
  next: SimOffseasonNextAction | null;
  picks_held: number;
  /** The incoming rookie class is simulated; strength is flavor (weak / average / strong). */
  rookie_class?: SimRookieClass;
}

/** One pick as the engine logs it (the `made` list of the draft calls). */
export interface SimRookiePickMade {
  n: number;
  round: number;
  pick: string;
  orig: string;
  team: string;
  pid: string;
  auto?: boolean;
}

export interface SimOffseasonResponse extends SimGameEnvelope {
  game?: SimGame;
  offseason?: SimOffseason;
  made?: SimRookiePickMade[];
}

export interface SimDynastyYear {
  season_no: number;
  year: number;
  rank: number;
  record: string;
  pf: number;
  playoff_result: string;
  champion: SimSeasonChampion | null;
  avg_age: number | null;
  top_scorers: SimTopScorer[];
}

export interface SimDynastySummary {
  mode: "dynasty";
  seasons_total: number;
  seasons_played: number;
  start_year: number;
  complete: boolean;
  titles: number;
  playoff_trips: number;
  avg_finish: number | null;
  wins: number;
  losses: number;
  best_season: { year: number; rank: number; record: string } | null;
  by_year: SimDynastyYear[];
  rookie_drafts?: { year: number; picks: unknown[] }[];
  picks_held: number;
}

export interface SimDynastyResponse extends SimGameEnvelope {
  dynasty?: SimDynastySummary;
  game?: SimGame;
}

// --- picks

const PICK_ID = /^pick:(\d{4}):(\d+):(.+)$/;

export function simIsPickId(id: string | null | undefined): boolean {
  return typeof id === "string" && PICK_ID.test(id);
}

/** Type guard for a trade asset that is a pick (kind "pick", or a pick id). */
export function simIsPick(asset: Pick<SimTradeAsset, "id"> & { kind?: string }): asset is SimPickAsset {
  return asset.kind === "pick" || simIsPickId(asset.id);
}

export function simParsePickId(id: string): { season: number; round: number; origTeamId: string } | null {
  const m = PICK_ID.exec(id);
  return m ? { season: Number(m[1]), round: Number(m[2]), origTeamId: m[3] } : null;
}

const HINT_WORD: Record<SimPickSlotHint, string> = { early: "early", mid: "mid", late: "late" };

/** "2027 Round 1 (early)": the slot hint is only known for the next draft. */
export function simPickLabelText(pick: Pick<SimPickAsset, "id"> & Partial<Pick<SimPickAsset, "season" | "round" | "slot_hint">>): string {
  const parsed = simParsePickId(pick.id);
  const season = pick.season ?? parsed?.season;
  const round = pick.round ?? parsed?.round;
  if (season == null || round == null) return "Draft pick";
  const hint = pick.slot_hint ? ` (${HINT_WORD[pick.slot_hint]})` : "";
  return `${season} Round ${round}${hint}`;
}

/** "2029 R3 (early)": the compact form for a trade-side chip, where the full label gets cut off at phone width. */
export function simPickChipText(pick: Pick<SimPickAsset, "id"> & Partial<Pick<SimPickAsset, "season" | "round" | "slot_hint">>): string {
  const parsed = simParsePickId(pick.id);
  const season = pick.season ?? parsed?.season;
  const round = pick.round ?? parsed?.round;
  if (season == null || round == null) return "Draft pick";
  const hint = pick.slot_hint ? ` (${HINT_WORD[pick.slot_hint]})` : "";
  return `${season} R${round}${hint}`;
}

/** Plain explanation of the early / mid / late hint ("Projected near the top of the round"). */
export function simPickSlotHint(pick: Pick<SimPickAsset, "slot_hint" | "season">, draftYear?: number | null): string {
  if (pick.slot_hint === "early") return "Projected near the top of the round.";
  if (pick.slot_hint === "late") return "Projected near the bottom of the round.";
  if (pick.slot_hint === "mid") return "Projected in the middle of the round.";
  if (draftYear != null && pick.season > draftYear) return "Slot is set after that season.";
  return "Slot not set yet.";
}

/** "via Rivals" when a pick came from another team, else null. */
export function simPickViaLine(pick: Pick<SimPickAsset, "orig_team_id" | "orig_team_name" | "own" | "owner">): string | null {
  if (pick.own === true) return null;
  if (pick.own === false) return `via ${pick.orig_team_name}`;
  const holder = pick.owner?.team_id;
  return holder && holder !== pick.orig_team_id ? `via ${pick.orig_team_name}` : null;
}

export interface SimPickYearGroup {
  season: number;
  rounds: { round: number; picks: SimPickAsset[] }[];
  count: number;
}

/** Picks grouped by year, then round (oldest year first, round 1 first). */
export function simPickGroups(picks: SimPickAsset[] | null | undefined): SimPickYearGroup[] {
  const byYear = new Map<number, Map<number, SimPickAsset[]>>();
  for (const pick of picks ?? []) {
    const rounds = byYear.get(pick.season) ?? new Map<number, SimPickAsset[]>();
    rounds.set(pick.round, [...(rounds.get(pick.round) ?? []), pick]);
    byYear.set(pick.season, rounds);
  }
  return [...byYear.entries()]
    .sort((a, b) => a[0] - b[0])
    .map(([season, rounds]) => {
      const list = [...rounds.entries()].sort((a, b) => a[0] - b[0]).map(([round, ps]) => ({ round, picks: ps }));
      return { season, rounds: list, count: list.reduce((n, r) => n + r.picks.length, 0) };
    });
}

/** The picks a team holds, from GET /picks. */
export function simPicksOf(res: Pick<SimPicksResponse, "teams" | "you"> | null | undefined, teamId: string | null | undefined): SimPickAsset[] {
  if (!res) return [];
  if (!teamId) return res.you ?? [];
  return res.teams?.find((t) => t.team_id === teamId)?.picks ?? res.you?.filter((p) => p.owner?.team_id === teamId) ?? [];
}

/** One line for the collapsed "Your picks" summary: "6 picks: 2027 (2), 2028 (2), 2029 (2)". */
export function simPicksSummaryLine(picks: SimPickAsset[] | null | undefined): string {
  const groups = simPickGroups(picks);
  const total = groups.reduce((n, g) => n + g.count, 0);
  if (total === 0) return "No picks";
  return `${total} pick${total === 1 ? "" : "s"}: ${groups.map((g) => `${g.season} (${g.count})`).join(", ")}`;
}

/** Display fields for any trade asset (player or pick) in a chip or list. */
export function simAssetTitle(asset: SimTradeAsset): string {
  return simIsPick(asset) ? simPickLabelText(asset) : asset.name;
}

// --- IR and taxi

export interface SimMoveCheck {
  ok: boolean;
  /** The backend reason code this would be refused with (when not ok). */
  reason?: "ir_full" | "ir_ineligible" | "taxi_full" | "taxi_ineligible" | "roster_full" | "reserves_unavailable";
}

export interface SimMoveContext {
  reserves: SimReserves | null | undefined;
  rosterSize?: number | null;
  rosterLimit?: number | null;
}

/** True when the game has an IR or taxi squad (older saves and redraft games without slots do not). */
export function simReservesOn(settings: Partial<SimGameSettings> | null | undefined, reserves?: SimReserves | null): boolean {
  if (reserves) return Boolean(reserves.enabled) && (reserves.ir_slots > 0 || reserves.taxi_slots > 0);
  return Boolean(settings?.reserve_v) && ((settings?.ir_slots ?? 0) > 0 || (settings?.taxi_slots ?? 0) > 0);
}

function squadOf(player: Pick<SimGamePlayer, "squad">): SimSquad {
  return player.squad ?? "roster";
}

/** Mirrors the engine's check order for a move to IR (modules/sim/game_actions.py check_move). */
export function simCanMoveToIr(player: Pick<SimGamePlayer, "squad" | "status" | "out_weeks">, ctx: SimMoveContext): SimMoveCheck {
  const r = ctx.reserves;
  if (!r || !r.enabled) return { ok: false, reason: "reserves_unavailable" };
  if (squadOf(player) === "ir") return { ok: false };
  if (r.ir_slots <= 0 || r.ir_used >= r.ir_slots) return { ok: false, reason: "ir_full" };
  if (squadOf(player) !== "roster") return { ok: false, reason: "ir_ineligible" };
  if (!(player.out_weeks > 0 || player.status === "out")) return { ok: false, reason: "ir_ineligible" };
  return { ok: true };
}

export function simCanMoveToTaxi(player: Pick<SimGamePlayer, "squad" | "pos" | "taxi_eligible">, ctx: SimMoveContext): SimMoveCheck {
  const r = ctx.reserves;
  if (!r || !r.enabled) return { ok: false, reason: "reserves_unavailable" };
  if (squadOf(player) === "taxi") return { ok: false };
  if (r.taxi_slots <= 0 || r.taxi_used >= r.taxi_slots) return { ok: false, reason: "taxi_full" };
  if (squadOf(player) !== "roster") return { ok: false, reason: "taxi_ineligible" };
  if (!player.taxi_eligible || !simTradable(player.pos)) return { ok: false, reason: "taxi_ineligible" };
  return { ok: true };
}

/** Activate (from IR) or promote (from taxi) needs an open roster spot. */
export function simCanMoveToRoster(player: Pick<SimGamePlayer, "squad">, ctx: SimMoveContext): SimMoveCheck {
  if (!ctx.reserves || !ctx.reserves.enabled) return { ok: false, reason: "reserves_unavailable" };
  if (squadOf(player) === "roster") return { ok: false };
  if (ctx.rosterSize != null && ctx.rosterLimit != null && ctx.rosterSize >= ctx.rosterLimit) return { ok: false, reason: "roster_full" };
  return { ok: true };
}

export type SimReserveMoveTo = "roster" | "ir" | "taxi";

export interface SimReserveAction {
  to: SimReserveMoveTo;
  label: string;
  check: SimMoveCheck;
}

/** The menu for one player: only moves that make sense from where he sits, each with its legality. */
export function simReserveActions(player: SimGamePlayer, ctx: SimMoveContext): SimReserveAction[] {
  const squad = squadOf(player);
  if (squad === "ir") return [{ to: "roster", label: "Activate", check: simCanMoveToRoster(player, ctx) }];
  if (squad === "taxi") return [{ to: "roster", label: "Promote", check: simCanMoveToRoster(player, ctx) }];
  return [
    { to: "ir", label: "Move to IR", check: simCanMoveToIr(player, ctx) },
    { to: "taxi", label: "Move to taxi", check: simCanMoveToTaxi(player, ctx) },
  ];
}

/** Why a move is not allowed, in plain words (the backend `message` wins when there is one). */
export function simReserveReasonText(reason: string | null | undefined, message?: string | null): string {
  if (message) return message;
  return simGameReasonMessage(reason ?? "");
}

/** "IR 1 of 2" / "Taxi 3 of 4". */
export function simReserveUsedLine(kind: "ir" | "taxi", reserves: SimReserves | null | undefined): string {
  if (!reserves) return "";
  const used = kind === "ir" ? reserves.ir_used : reserves.taxi_used;
  const slots = kind === "ir" ? reserves.ir_slots : reserves.taxi_slots;
  return `${kind === "ir" ? "IR" : "Taxi"} ${used} of ${slots}`;
}

export interface SimPlayerChipSpec {
  key: "ir" | "taxi" | "rookie" | "out";
  label: string;
  tone: SimGameTone;
}

/** Status chips for a roster row: IR, TAXI, ROOKIE, OUT n wks. */
export function simPlayerChips(player: Pick<SimGamePlayer, "squad" | "rookie" | "status" | "out_weeks">): SimPlayerChipSpec[] {
  const chips: SimPlayerChipSpec[] = [];
  const squad = squadOf(player);
  if (squad === "ir") chips.push({ key: "ir", label: "IR", tone: "danger" });
  if (squad === "taxi") chips.push({ key: "taxi", label: "TAXI", tone: "accent" });
  if (player.rookie) chips.push({ key: "rookie", label: "ROOKIE", tone: "success" });
  if (player.out_weeks > 0) chips.push({ key: "out", label: `OUT ${player.out_weeks} ${player.out_weeks === 1 ? "wk" : "wks"}`, tone: "danger" });
  return chips;
}

// --- offseason

const OFFSEASON_STAGES: SimOffseasonStage[] = ["review", "rookie_draft", "cutdown"];

export function simOffseasonStageLabel(stage: SimOffseasonStage | null | undefined): string {
  switch (stage) {
    case "review":
      return "Review";
    case "rookie_draft":
      return "Rookie draft";
    case "cutdown":
      return "Roster check";
    default:
      return "Offseason";
  }
}

/** The three offseason steps with which is done, current or still ahead. */
export function simOffseasonSteps(stage: SimOffseasonStage | null | undefined): { key: SimOffseasonStage; label: string; state: "done" | "current" | "todo" }[] {
  const at = stage ? OFFSEASON_STAGES.indexOf(stage) : 0;
  return OFFSEASON_STAGES.map((key, i) => ({ key, label: simOffseasonStageLabel(key), state: i < at ? "done" : i === at ? "current" : "todo" }));
}

export interface SimOffseasonCta {
  /** Which call the button makes; null when nothing is left to press (the draft is the work). */
  action: SimOffseasonNextAction | null;
  label: string;
  /** Plain reason the button is disabled. */
  blocked: string | null;
}

/** The one big button for the current stage. */
export function simOffseasonCta(off: Pick<SimOffseason, "stage" | "season_no" | "roster"> | null | undefined): SimOffseasonCta {
  if (!off) return { action: null, label: "", blocked: null };
  if (off.stage === "review") return { action: "start_rookie_draft", label: "Start rookie draft", blocked: null };
  if (off.stage === "rookie_draft") return { action: "finish_draft", label: "Auto-draft the rest", blocked: null };
  const cuts = off.roster?.cuts_needed ?? 0;
  return {
    action: "start_season",
    label: cuts > 0 ? "Finish cut-down" : `Start season ${off.season_no + 1}`,
    blocked: cuts > 0 ? `Cut ${cuts} player${cuts === 1 ? "" : "s"} to get to the roster limit first.` : null,
  };
}

/** "Offseason after 2026" heading for the screen. */
export function simOffseasonHeading(off: Pick<SimOffseason, "last_season" | "season_no" | "seasons"> | null | undefined): string {
  if (!off) return "Offseason";
  const year = off.last_season?.year;
  return year ? `Offseason after ${year}` : `Offseason after season ${off.season_no}`;
}

/** "Season 2 of 5 is next" style line. */
export function simOffseasonProgressLine(off: Pick<SimOffseason, "season_no" | "seasons" | "year"> | null | undefined): string {
  if (!off) return "";
  const next = off.season_no + 1;
  return `Season ${next} of ${off.seasons} is next (${off.year}).`;
}

/** The draft clock as a banner line. */
export function simRookieClockLine(draft: Pick<SimOffseason["draft"], "on_clock" | "your_turn" | "total" | "pick_index">): string {
  if (!draft.on_clock) return draft.pick_index >= draft.total && draft.total > 0 ? "Rookie draft complete." : "Rookie draft not started.";
  const c = draft.on_clock;
  if (draft.your_turn) return `You are on the clock: round ${c.round}, pick ${c.n} of ${draft.total}.`;
  return `${c.team_name ?? "An AI team"} is on the clock: round ${c.round}, pick ${c.n} of ${draft.total}.`;
}

/** "Round 1, pick 4" for one of your picks in the order. */
export function simRookiePickLine(row: Pick<SimRookieOrderRow, "round" | "n" | "traded" | "orig_team_name" | "made">): string {
  const base = `Round ${row.round}, pick ${row.n}`;
  const via = row.traded ? ` (via ${row.orig_team_name})` : "";
  return row.made ? `${base}${via}: ${row.made.name}` : `${base}${via}`;
}

export function simAgeDeltaTone(delta: number): SimGameTone {
  if (delta >= 0.5) return "success";
  if (delta <= -0.5) return "danger";
  return "muted";
}

/** Aging arrow and signed points change for a mover row. */
export function simMoverText(row: Pick<SimOffseasonMover, "delta" | "age_before" | "age_after" | "mean_before" | "mean_after">): {
  arrow: string;
  delta: string;
  age: string;
  tone: SimGameTone;
} {
  const tone = simAgeDeltaTone(row.delta);
  const arrow = tone === "success" ? "▲" : tone === "danger" ? "▼" : "–";
  const sign = row.delta > 0 ? "+" : row.delta < 0 ? "-" : "";
  const age = row.age_before != null && row.age_after != null ? `${row.age_before} to ${row.age_after}` : "";
  return { arrow, delta: `${sign}${Math.abs(row.delta).toFixed(1)}`, age, tone };
}

/** Your retirees first, then the rest. */
export function simRetireesSorted(rows: SimOffseasonRetiree[] | null | undefined): SimOffseasonRetiree[] {
  return [...(rows ?? [])].sort((a, b) => Number(b.is_yours) - Number(a.is_yours) || (b.market ?? 0) - (a.market ?? 0) || a.name.localeCompare(b.name));
}

// --- dynasty summary

export function simOrdinal(n: number): string {
  return `${n}${simOrdinalSuffix(n)}`;
}

/** "5 of 5 seasons" style progress for a dynasty game. */
export function simDynastyProgressLine(d: Pick<SimDynastyBlock, "season_no" | "seasons" | "year"> | null | undefined): string {
  if (!d) return "";
  return `Season ${d.season_no} of ${d.seasons} (${d.year})`;
}

export interface SimDynastyYearView {
  year: number;
  seasonNo: number;
  record: string;
  finish: string;
  result: string;
  resultTone: SimGameTone;
  champion: string;
  youWon: boolean;
  scorers: string;
}

/** One per-year row, ready to render (every field a string). */
export function simDynastyYearView(y: SimDynastyYear): SimDynastyYearView {
  const youWon = Boolean(y.champion?.is_you);
  return {
    year: y.year,
    seasonNo: y.season_no,
    record: y.record,
    finish: simOrdinal(y.rank),
    result: simPlayoffResultLabel(y.playoff_result),
    resultTone: simPlayoffOutcomeTone(y.playoff_result),
    champion: y.champion ? `${y.champion.name}${youWon ? " (you)" : ""}` : "No champion",
    youWon,
    scorers: (y.top_scorers ?? []).map((s) => `${s.name} ${s.pts.toFixed(1)}`).join(", "),
  };
}

export interface SimDynastySummaryView {
  titles: number;
  titlesLine: string;
  avgFinish: string;
  bestSeason: string;
  trips: string;
  record: string;
  years: SimDynastyYearView[];
  seasonsLine: string;
}

/** The dynasty result card, shaped: nothing crashes on a missing summary or empty year list. */
export function simDynastySummaryView(d: SimDynastySummary | null | undefined): SimDynastySummaryView {
  const years = (d?.by_year ?? []).map(simDynastyYearView);
  const titles = d?.titles ?? 0;
  return {
    titles,
    titlesLine: titles === 0 ? "No titles yet" : `${titles} title${titles === 1 ? "" : "s"}`,
    avgFinish: d?.avg_finish != null ? d.avg_finish.toFixed(1) : "-",
    bestSeason: d?.best_season ? `${d.best_season.year}: ${simOrdinal(d.best_season.rank)} at ${d.best_season.record}` : "-",
    trips: d ? `${d.playoff_trips} of ${d.seasons_played}` : "-",
    record: d ? `${d.wins}-${d.losses}` : "-",
    years,
    seasonsLine: d ? `${d.seasons_played} of ${d.seasons_total} seasons played` : "",
  };
}

/** A finished season's archive as a per-year row (the offseason strip uses the same shape as the summary). */
export function simArchiveToYear(a: SimSeasonArchive): SimDynastyYear {
  const you = a.you;
  return {
    season_no: a.season_no,
    year: a.year,
    rank: you.rank,
    record: `${you.wins}-${you.losses}${you.ties ? `-${you.ties}` : ""}`,
    pf: you.pf,
    playoff_result: you.playoff_result,
    champion: a.champion,
    avg_age: you.avg_age,
    top_scorers: you.top_scorers ?? [],
  };
}

/** True when the result payload is a dynasty one (grade and review are null there). */
export function simIsDynastyResult(result: SimGameResult | null | undefined): boolean {
  return result?.mode === "dynasty" || Boolean(result?.dynasty);
}
