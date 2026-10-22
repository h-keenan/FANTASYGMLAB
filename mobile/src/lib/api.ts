import { AppState } from 'react-native';

import { supabase } from './supabase';
import { env } from './env';
import { maskShowcaseFields, setShowcaseModeEnabled } from './showcaseMode';
import { withBackgroundRetry } from './backgroundRetry';
import type { PercentileExplorerResponse } from './percentileExplorer';
import type { LeaguesGlanceResponse } from './leaguesGlance';
import type {
  ManagerTendenciesDetailResponse,
  ManagerTendenciesSummaryResponse,
} from './managerTendencies';

/**
 * Client for services/mobile_api_service.py. Every call attaches the current
 * Supabase session's access token as a Bearer header — the API verifies it
 * against GoTrue on each request (see the service's docstring). No token,
 * no request: callers should only reach authenticated screens once signed in.
 */

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

// See backgroundRetry.ts for why this exists: a request mid-flight when the
// app backgrounds can come back as a bare transport failure once the app
// resumes, and nothing else re-triggers it (useFocusEffect is React
// Navigation focus, not OS foreground/background). Tracking transitions
// here — the single choke point every API call already funnels through —
// lets authorizedRequest retry that one case transparently instead of every
// screen's fetch needing its own AppState awareness.
let backgroundTransitions = 0;
AppState.addEventListener('change', (nextState) => {
  if (nextState !== 'active') backgroundTransitions += 1;
});

// A screen like League Overview fires several of these in parallel
// (Promise.all) and each individual call is usually wrapped in its own
// `.catch(() => null)` by the caller, so a single endpoint that never
// settles doesn't just degrade that one tile — it leaves the *whole*
// screen's loading state stuck forever, since `finally { setLoading(false) }`
// never runs. That's the actual failure mode behind "I swapped leagues and
// it's just loading": a newly-opened (cold-cache) league's heavier
// endpoints — e.g. playoff_simulator.build_league_playoff_odds_cached,
// waivers_ui's pool lock — run a real Redis single-flight lock with its own
// ~15s ceiling server-side (modules/redis_cache.py's
// redis_single_flight_cache), and a request can legitimately take tens of
// seconds for a league this device hasn't warmed up yet. Nothing on the
// client ever gave up, so a slow backend round-trip (or, if the server
// truly wedges, one that never returns at all) had no way to surface as a
// recoverable error instead of an infinite spinner.
//
// REQUEST_TIMEOUT_MS is comfortably above every known server-side lock
// ceiling (15s) so a legitimately slow cold computation still gets to
// finish, but still finite — once it fires, `fetch` rejects with an
// AbortError, which transportError.ts's `isAbortOrTimeoutError` (and, via
// it, `isTransportError`/`toUserErrorMessage`) already know how to turn
// into a friendly message. That classification existed before this fetch
// ever set a `signal` — this wires up the wrapper the comment there was
// already written for.
const REQUEST_TIMEOUT_MS = 30_000;

async function performRequest<T>(
  path: string,
  init: { method?: 'GET' | 'POST' | 'PATCH' | 'DELETE'; jsonBody?: unknown } | undefined,
  accessToken: string,
): Promise<T> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  let response: Response;
  try {
    response = await fetch(`${env.apiBaseUrl}${path}`, {
      method: init?.method ?? 'GET',
      headers: {
        Authorization: `Bearer ${accessToken}`,
        ...(init?.jsonBody !== undefined ? { 'Content-Type': 'application/json' } : {}),
      },
      ...(init?.jsonBody !== undefined ? { body: JSON.stringify(init.jsonBody) } : {}),
      signal: controller.signal,
    });
  } finally {
    clearTimeout(timeoutId);
  }

  let body: unknown = null;
  try {
    body = await response.json();
  } catch {
    // Non-JSON error body (e.g. a gateway timeout page) — fall through below.
  }

  if (!response.ok) {
    const message =
      body && typeof body === 'object' && 'error' in body
        ? String((body as { error: unknown }).error)
        : `Request failed (${response.status}).`;
    throw new ApiError(response.status, message);
  }

  return body as T;
}

async function authorizedRequest<T>(
  path: string,
  init?: { method?: 'GET' | 'POST' | 'PATCH' | 'DELETE'; jsonBody?: unknown },
): Promise<T> {
  const { data, error: sessionError } = await supabase.auth.getSession();
  if (sessionError || !data.session) {
    throw new ApiError(401, 'Not signed in.');
  }
  const accessToken = data.session.access_token;

  const backgroundSnapshot = backgroundTransitions;
  const body = await withBackgroundRetry(
    () => performRequest<T>(path, init, accessToken),
    () => backgroundTransitions > backgroundSnapshot,
  );

  // Single choke point for showcase mode (lib/showcaseMode.ts): every
  // successful response leaves through here, so masking identity fields at
  // this line covers every screen at once. A no-op unless a dev has the
  // toggle on — it returns the same reference back when the flag is off.
  return maskShowcaseFields(body as T);
}

function authorizedFetch<T>(path: string): Promise<T> {
  return authorizedRequest<T>(path);
}

function authorizedPost<T>(path: string, jsonBody: unknown): Promise<T> {
  return authorizedRequest<T>(path, { method: 'POST', jsonBody });
}

function authorizedDelete<T>(path: string): Promise<T> {
  return authorizedRequest<T>(path, { method: 'DELETE' });
}

function authorizedPatch<T>(path: string, jsonBody: unknown): Promise<T> {
  return authorizedRequest<T>(path, { method: 'PATCH', jsonBody });
}

export interface MeResponse {
  ok: true;
  user: {
    id: string;
    email: string;
    entitlement: 'free' | 'premium';
    sleeper_username: string;
    // "error" means `entitlement` above is a fail-closed default because the
    // profile lookup itself failed — not necessarily this user's real plan.
    profile_status: 'ok' | 'error';
    // Saved leagues this plan allows (modules/saved_leagues.py). Server-sent
    // rather than hardcoded here so the cap lives in exactly one place.
    league_cap: number;
  };
  // Canonical Premium benefit copy — sourced from modules/premium_page.py
  // (PREMIUM_INCLUDED_NOW / MOBILE_PREMIUM_BENEFIT_LINES), the same list web's
  // Premium page renders. PaywallScreen renders these instead of an
  // independently-authored local copy; see its own hardcoded fallback for
  // when this request fails.
  premium_benefits?: string[];
}

/** One Sleeper league behind a username, for the add-league picker. */
export interface SleeperLeagueOption {
  league_id: string;
  name: string;
  season: string;
  total_rosters: number;
}

export interface SleeperLeagueLookupResponse {
  ok: boolean;
  // Mirrors modules/sleeper_leagues.py's LeagueLookupStatus.
  status: 'ok' | 'empty_username' | 'user_not_found' | 'no_leagues' | 'unavailable';
  username: string;
  leagues: SleeperLeagueOption[];
  // Customer-safe copy for a non-"ok" status — show it verbatim.
  message: string;
}

export type SaveLeagueReason =
  | ''
  | 'at_cap'
  | 'league_not_found'
  | 'not_available'
  // ESPN leagues only (modules/espn_leagues.py).
  | 'espn_team_not_selected'
  | 'mapping_too_low';

/** POST /v1/espn/leagues/preview. Public ESPN leagues only;
 * `league.league_key` is the id POST /v1/leagues/save takes. */
export interface EspnLeagueTeam {
  roster_id: string;
  team_name: string;
  owner_name: string;
  player_count: number;
  matched_player_count: number;
}

export interface EspnLeaguePreviewResponse {
  ok: boolean;
  reason: string;
  message: string;
  league?: { league_key: string; espn_league_id: string; season: string; name: string; team_count: number };
  teams?: EspnLeagueTeam[];
  diagnostics?: {
    teams_found: number;
    total_espn_players_seen: number;
    canonical_matched_count: number;
    unmatched_count: number;
    matched_rate: number;
  };
  features?: Array<{ feature: string; status: 'available' | 'not_available'; note: string }>;
}

export interface SaveLeagueResponse {
  ok: boolean;
  reason: SaveLeagueReason;
  // How many leagues this account's plan may keep (see MeResponse.league_cap).
  cap: number;
  // True when the server started warming this league's first-load data;
  // follow it with getLeagueWarmupStatus.
  warming?: boolean;
  league?: {
    league_id: string;
    league_name: string;
    is_default: boolean;
  };
}

export interface MyRosterResponse {
  ok: true;
  roster: Record<string, unknown> | null;
  reason: '' | 'no_sleeper_username_linked' | 'sleeper_user_not_found' | 'not_a_member_of_league';
}

export interface LeagueResponse {
  ok: true;
  league: Record<string, unknown>;
}

export interface LeagueUsersResponse {
  ok: true;
  users: Array<Record<string, unknown>>;
}

export interface LeagueRostersResponse {
  ok: true;
  rosters: Array<Record<string, unknown>>;
}

export interface TeamProfile {
  team_name: string;
  owner_name: string;
  username: string;
  avatar_id: string;
  avatar_url: string;
  roster_id: number | string;
  owner_id: string;
}

export interface LeagueTeamProfilesResponse {
  ok: true;
  profiles: Record<string, TeamProfile>;
}

export interface TeamRanking {
  roster_id: string;
  team_name: string | null;
  owner_name: string | null;
  owner_username: string | null;
  avatar_url: string | null;
  wins: number | null;
  losses: number | null;
  ties: number | null;
  record_label: string | null;
  points_for: number | null;
  points_against: number | null;
  power_rank: number | null;
  power_rank_tied: boolean;
  franchise_rank: number | null;
  franchise_rank_tied: boolean;
  draft_capital_rank: number | null;
  draft_capital_rank_tied: boolean;
  starter_rank: number | null;
  starter_rank_tied: boolean;
  bench_rank: number | null;
  bench_rank_tied: boolean;
  age_rank: number | null;
  age_rank_tied: boolean;
  average_age: number | null;
  strategy: string | null;
  strategy_label: string | null;
  archetype: string | null;
  archetype_label: string | null;
  archetype_explanation: string | null;
  archetype_strengths: string[];
  archetype_risks: string[];
  archetype_recommendations: string[];
  // Real buy/sell pattern read off this team's actual Sleeper trade
  // history (modules.team_trade_history) — "Seller"/"Buyer"/"Neutral".
  // Context, not a new rank; Neutral covers both "no lean" and "not
  // enough trade history yet."
  trade_tendency: string;
  trade_tendency_sell_count: number;
  trade_tendency_buy_count: number;
  // Real season-to-date move count off actual Sleeper transaction history
  // (modules.manager_activity) — trades + waiver claims + free-agent moves
  // this roster has been party to so far this season. Powers the Dashboard
  // League Pulse "Most Active Manager" tile.
  transaction_activity_count: number;
  // Real future-1st-round-pick flow off actual Sleeper trade history
  // (modules.pick_flow) — backs the "Pick Hoarder"/"Pick Seller" entry in
  // team_badges below.
  firsts_acquired: number;
  firsts_sent: number;
  // Real current win/loss streak off actual weekly matchup results
  // (modules.team_streaks) — positive = active win streak, negative =
  // active losing streak. Backs the "Hot Streak"/"Cold Streak" entry in
  // team_badges below.
  current_streak: number;
  // Zero, one, or several real, data-backed team signals (Highly Active /
  // Quiet Manager, Pick Hoarder / Pick Seller, Veteran Collector / Youth
  // Builder, Hot Streak / Cold Streak, Top-Heavy Roster) — see
  // TEAM_BADGE_VISUALS in TeamsScreen.tsx for how each label renders.
  team_badges: string[];
}

export interface LeagueTeamRankingsResponse {
  ok: true;
  teams: TeamRanking[];
  reason: string;
}

// Real Monte-Carlo rest-of-season simulation result for one team — see
// modules.playoff_simulator's module docstring (backend) for the full
// methodology. `clinched`/`eliminated` are only ever true at exactly
// 100/0 — that's a structural property of the simulation, not a rounded
// display convenience, so the UI can treat them as hard facts.
export interface PlayoffOddsTeam {
  roster_id: string;
  team_name: string;
  owner_name: string | null;
  avatar_url: string | null;
  record_label: string | null;
  playoff_probability: number;
  median_final_wins: number;
  median_final_losses: number;
  median_seed: number;
  remaining_games: number;
  clinched: boolean;
  eliminated: boolean;
}

export interface PlayoffOddsResponse {
  ok: true;
  reason: string;
  teams: PlayoffOddsTeam[];
  playoff_teams?: number;
  current_week?: number;
  regular_season_end?: number;
  weeks_remaining?: number;
  trials?: number;
  slope_fitted?: boolean;
  games_used_for_fit?: number;
  season?: string;
}

export interface DraftPosture {
  label: string;
  note: string;
  tone: string;
  draft_capital_rank: number | null;
  draft_capital_rank_tied: boolean;
  draft_capital: number | null;
  future_draft_capital_rank: number | null;
  future_draft_capital_rank_tied: boolean;
  future_draft_capital: number | null;
  strategy_display: string | null;
  power_rank: number | null;
  power_rank_tied: boolean;
  franchise_rank: number | null;
  franchise_rank_tied: boolean;
  first_rounders: number | null;
  pick_count: number | null;
}

export interface DraftCard {
  label: string;
  title: string;
  tone: string;
  items: string[];
}

export interface DraftCenterResponse {
  ok: true;
  reason: string;
  posture: DraftPosture | null;
  posture_reason: string;
  decision_cards: DraftCard[];
  partner_cards: DraftCard[];
}

export interface LineupPlayer {
  player_id: string;
  name: string | null;
  position: string | null;
  team: string | null;
  age: number | null;
  status: string | null;
  injury_status: string | null;
  /**
   * The injury tag to render — '' when healthy.
   *
   * Render THIS, never `injury_status` on its own: a weekly tag arrives on
   * `injury_status` ("Questionable"), but IR/PUP/season-ending arrives on
   * `status` with `injury_status` blank, so an `injury_status`-driven pill
   * silently hides the most unavailable players. The server resolves both
   * into one label (modules.rankings.injury_display_label).
   */
  injury_label: string;
  /** Confirmed unavailable (Out/IR/PUP) — only ever a starter when no available alternative exists. */
  ruled_out: boolean;
  tier: string | null;
  score: number | null;
  slot: string | null;
  suggested_starter: boolean;
  /**
   * Where this player actually sits in Sleeper — 'ir' or 'taxi' when the
   * manager placed them in that slot, else 'starter'/'bench' from the same
   * suggested-lineup split as `suggested_starter`. A DIFFERENT concept from
   * `injury_label`: a player can be `injury_label: 'Out'` while sitting in
   * a plain bench slot, or genuinely IR-placed while healthy-labeled.
   * Optional only for older cached responses; treat missing as 'bench' for
   * a non-starter.
   */
  roster_slot?: 'starter' | 'bench' | 'ir' | 'taxi';
  opportunity_label: string | null;
  /** 0-99 "OVR" badge — percentiled against the full league-eligible pool
   * at this position (not just this roster), same curve/gate as
   * QuickViewStats.overall_rating. Null when that position's pool was too
   * thin to rank against. */
  overall_rating: number | null;
  /** In-season weekly lineup gate: 'Bye' / 'Out' / 'IR' / 'PUP' /
   * 'Suspended' when this player can't start this week, else null. Absent
   * from older API builds. See lib/lineupAvailability.ts. */
  start_ineligible_reason?: string | null;
  on_bye?: boolean;
  game_locked?: boolean;
  /** The points figure this week's lineup ranked him on, and its source. */
  lineup_points?: number | null;
  lineup_points_basis?: 'projection' | 'value_estimate' | 'value' | null;
}

export type LineupBasis = 'season_value' | 'weekly_projection' | 'weekly_availability';

/** League trade-window state from Sleeper's settings.trade_deadline
 * (backend: modules.league_calendar.trade_window). Additive — absent on
 * older servers. Trades are allowed through `trade_deadline_week`; once an
 * in-season league's current week passes it, `trade_deadline_passed` is
 * true and `message` carries the user-facing copy. */
export interface TradeWindow {
  trade_deadline_week: number | null;
  current_week: number | null;
  trade_deadline_passed: boolean;
  message: string;
}

export interface KeeperPlayerInfo {
  is_keeper: boolean;
  kept_round: number | null;
  cost_round: number | null;
  cost_source: 'keeper_pick' | 'last_draft_round' | null;
  /** Estimated: player value minus the typical value at the cost round. */
  surplus: number | null;
}

export interface KeeperCandidate {
  player_id: string;
  name: string;
  position: string;
  team: string;
  value: number;
  cost_round: number;
  cost_source: string;
  surplus: number;
  is_keeper: boolean;
  reason: string;
}

export interface KeepersResponse {
  ok: boolean;
  is_keeper_league: boolean;
  reason?: string;
  estimate_note?: string;
  players?: Record<string, KeeperPlayerInfo>;
  candidates?: KeeperCandidate[];
  recommended_ids?: string[];
  keep_count?: number;
  keep_count_basis?: 'league_setting' | 'previous_draft' | 'declared_keepers' | 'unknown';
  unpriced_count?: number;
}

export interface PositionNeedGroup {
  position: string;
  classification: 'covered' | 'short_term_need' | 'future_risk' | string;
  reasons: string[];
  upgrade_opportunity: boolean;
  temporary_injury_pressure: boolean;
}

/** GET .../my-team-needs: the per-position room assessments My Team's Team Analysis reads. */
export interface MyTeamNeedsResponse {
  ok: boolean;
  reason: string;
  strengths: string[];
  weaknesses: string[];
  position_groups: PositionNeedGroup[];
}

export interface MyTeamResponse {
  ok: true;
  starters: LineupPlayer[];
  bench: LineupPlayer[];
  reason: string;
  roster_id?: string;
  /** NFL week the suggested lineup is for (null in the offseason). */
  week?: number | null;
  lineup_basis?: LineupBasis;
  lineup_basis_label?: string;
  /** Starting slots left open: nobody eligible this week (bye / ruled out). */
  open_slots?: string[];

  /** Sleeper settings.best_ball — Sleeper sets the lineup itself, so the
   * suggested starters/bench split is replaced by one roster list. */
  best_ball?: boolean;
  lineup_advice_message?: string;
  trade_window?: TradeWindow;
}

/**
 * A suggested starter on the weekly matchup screen.
 *
 * `score` here is the same season-long value/opportunity signal the rest of
 * the app uses — deliberately NOT a weekly points projection. This codebase
 * has no weekly-projection feed and no opponent-defense-strength data, so
 * nothing on this type may be renamed to imply either (see
 * SEASON_VALUE_BASIS_LABEL in services/mobile_api_service.py).
 */
export interface MatchupStarter extends LineupPlayer {
  /** Season-form reasoning: tier, workload/opportunity label, season-value rank, injury tag. */
  why: string;
  /** This week's projection; null when no projection context exists. */
  projection?: PlayerWeekProjection | null;
  /** Real points this week (Sleeper players_points); null before lineups post. */
  actual_points?: number | null;
  game_started?: boolean | null;
  game_status?: MatchupGameStatus | null;
}

/** modules.nfl_schedule.game_phase for one player's own NFL game. */
export type MatchupGameStatus = 'scheduled' | 'in_progress' | 'final';

/**
 * A player Sleeper reports as ACTUALLY starting this week for this roster —
 * real data, not a recommendation. Unlike `MatchupStarter`, `score` here is
 * still the season-value signal (for identity/context), but `actual_points`
 * is this player's REAL point total scored so far this week (live during
 * in-progress games, final once the week completes).
 */
export interface MatchupRealStarter {
  player_id: string;
  name: string | null;
  position: string | null;
  team: string | null;
  age: number | null;
  status: string | null;
  injury_status: string | null;
  injury_label: string;
  tier: string | null;
  score: number | null;
  opportunity_label: string | null;
  overall_rating: number | null;
  /** This starter's real points scored so far this week. Null only if Sleeper didn't report a value for him. */
  actual_points: number | null;
  /** This week's per-game projection (modules.player_projections) — a
   * separate, clearly-labeled figure from `actual_points`, never a
   * substitute for it. Null when the projection enrichment couldn't run
   * (best-effort; see services/mobile_api_service.py's fails-soft
   * contract) — render nothing rather than a guess. */
  projection: PlayerWeekProjection | null;
  /**
   * Whether THIS player's own NFL game has actually kicked off this week —
   * distinct from `MatchupSide.has_live_data`, which only means Sleeper has
   * locked the week's starters, not that any individual player's game has
   * begun (games across a week start at different times). A starter whose
   * game hasn't started yet still reports `actual_points === 0` from
   * Sleeper, which is NOT a real score — a client must gate on this (not on
   * `actual_points`) before treating 0 as a genuine result. Sourced from
   * modules.nfl_schedule's real kickoff time for this player's team/week.
   * Null when the signal isn't available (no resolvable team, bye week,
   * schedule fetch hiccup) — treat as unknown, never as "started".
   */
  game_started: boolean | null;
  /** "scheduled" / "in_progress" / "final" for his own game; null when unknown. */
  game_status?: MatchupGameStatus | null;
  /** The league lineup slot he fills, named like the suggested lineup's slots. */
  slot?: string | null;
}

export interface MatchupSide {
  roster_id: string;
  team_name: string;
  owner_name: string | null;
  avatar_url: string | null;
  wins: number | null;
  losses: number | null;
  ties: number | null;
  starters: MatchupStarter[];
  /** Sum of this side's suggested starters' season-value scores. Not points. */
  season_value_total: number;
  /** Always the best-available lineup, for both sides — not necessarily the lineup Sleeper has set. */
  starters_basis: 'suggested_optimal_lineup';
  /** What this side's suggested lineup ranked on ('weekly_projection' in
   * season: byes/ruled-out never start). Absent from older API builds. */
  lineup_basis?: LineupBasis;
  lineup_basis_label?: string;
  /** Starting slots left open: nobody eligible this week (bye / ruled out). */
  open_slots?: string[];
  /**
   * This roster's ACTUAL current-week lineup, straight from Sleeper's own
   * matchup payload (`starters`/`starters_points`) — may differ from
   * `starters` above, which is this app's suggested best lineup. Empty when
   * `has_live_data` is false.
   */
  real_starters: MatchupRealStarter[];
  /** This roster's real point total for the week, from Sleeper. Null when `has_live_data` is false. */
  real_points: number | null;
  /**
   * False when Sleeper hasn't populated a real lineup for this roster yet
   * this week (matchup not started / not locked). Render `real_starters`/
   * `real_points` ONLY when this is true — otherwise they're empty/null by
   * design, not a real 0.
   */
  has_live_data: boolean;
  real_starters_basis: 'sleeper_actual_lineup';
  /** Starting slots this roster left unfilled in Sleeper. */
  real_empty_slots?: string[];
}

/** One position's expected-points edge between two lineups. */
export interface MatchupPositionEdge {
  position: string;
  my_points: number;
  opponent_points: number;
  edge: number;
  my_count: number;
  opponent_count: number;
  unmodeled: number;
}

export interface MatchupMovePlayer {
  player_id: string | null;
  name: string | null;
  position: string | null;
  team: string | null;
  tier: string | null;
  slot: string | null;
  points: number | null;
  projection_status: PlayerWeekProjection['status'] | null;
  injury_label: string;
}

/** One "start X over Y" change from the Sleeper lineup to the suggested one. Planner only. */
export interface MatchupSuggestedMove {
  slot: string;
  start: MatchupMovePlayer;
  over: MatchupMovePlayer | null;
  over_reason: 'bye_week' | 'ruled_out' | 'empty_slot' | null;
  gain: number | null;
  locked: boolean;
}

export type MatchupGameState = 'pregame' | 'live' | 'between_games' | 'final';

/** modules.matchup_win_probability output; `available` false when coverage is too thin. */
export interface MatchupWinProbability {
  available: boolean;
  reason?: 'no_starters' | 'insufficient_coverage';
  probability?: number;
  my_projected_total?: number;
  opponent_projected_total?: number;
}

export interface MatchupComparison {
  my_season_value: number;
  opponent_season_value: number;
  margin: number;
  edge: 'you' | 'opponent' | 'even';
  headline: string;
  basis: 'season_value';
  basis_label: string;
}

/** This week's REAL score comparison, from Sleeper's own live points. Null until both sides have `has_live_data`. */
export interface MatchupRealComparison {
  my_points: number;
  opponent_points: number;
  margin: number;
  edge: 'you' | 'opponent' | 'even';
  basis: 'sleeper_actual_lineup';
  basis_label: string;
}

export interface MatchupResponse {
  ok: true;
  /** Sleeper's current week (league settings.leg) — null when the league hasn't started one. */
  week: number | null;
  my_team: MatchupSide | null;
  opponent: MatchupSide | null;
  comparison: MatchupComparison | null;
  /** Real current-week score comparison — null when either side lacks live data yet. */
  real_comparison: MatchupRealComparison | null;
  basis: 'season_value';
  basis_label: string;
  reason: string;
  win_probability?: MatchupWinProbability | null;
  game_state?: MatchupGameState | null;
  position_edges?: { actual: MatchupPositionEdge[] | null; suggested: MatchupPositionEdge[] } | null;
  suggested_moves?: MatchupSuggestedMove[] | null;
  /** Sleeper settings.best_ball — suggested-lineup sections are hidden. */
  best_ball?: boolean;
  lineup_advice_message?: string;
}

/** One slot of a proposed lineup sent to POST .../matchup/what-if. */
export interface MatchupWhatIfSlot {
  slot: string;
  player_id: string | null;
}

export interface MatchupWhatIfBullet {
  tone: 'pro' | 'con' | 'neutral';
  text: string;
}

/** One roster player who could fill the slot being edited, with pros and cons
 * computed server-side (modules.matchup_what_if). Bye / out / locked players
 * come back with `selectable: false`. */
export interface MatchupWhatIfCandidate {
  player: MatchupStarter;
  selectable: boolean;
  /** True when this player is already in the lineup (he would trade places). */
  currently_starting?: boolean;
  blocked_reason: 'bye' | 'out' | 'locked' | null;
  points_delta: number | null;
  /** Whole-percent change in this matchup's win probability. */
  win_probability_delta: number | null;
  win_probability_after: MatchupWinProbability | null;
  bullets: MatchupWhatIfBullet[];
}

export interface MatchupWhatIfResponse {
  ok: boolean;
  reason: string;
  best_ball?: boolean;
  /** The edited lineup's starters (empty slots omitted). */
  lineup?: MatchupStarter[];
  win_probability?: MatchupWinProbability;
  position_edges?: MatchupPositionEdge[];
  candidates?: {
    slot: string;
    slot_locked: boolean;
    current_player_id: string | null;
    candidates: MatchupWhatIfCandidate[];
  } | null;
}

export interface PlayerSummary {
  full_name: string | null;
  first_name: string | null;
  last_name: string | null;
  position: string | null;
  team: string | null;
  status: string | null;
  injury_status: string | null;
  age: number | null;
  number: number | null;
  years_exp: number | null;
}

export interface PlayersResponse {
  ok: true;
  players: Record<string, PlayerSummary>;
}

export interface RankedPlayer {
  player_id: string;
  name: string | null;
  position: string | null;
  team: string | null;
  age: number | null;
  status: string | null;
  injury_status: string | null;
  tier: string | null;
  score: number | null;
  overall_rank: number | null;
  position_rank: number | null;
  rank_unavailable_reason: string | null;
  opportunity_label: string | null;
  // Optional rather than `| null` because several screens (Waivers, Alerts,
  // Trade Hub, MyTeam, TeamRoster) hand-build a lean player of this shape
  // from their own payloads to navigate into Player Detail; only the real
  // /rankings wire rows carry this, and Player Detail fetches its own copy
  // from /quick-view regardless.
  usage_trend?: UsageTrend | null;
  /** 0-99 "OVR" badge — percentiled against the full ranked pool at this
   * position, same curve/gate as QuickViewStats.overall_rating. Null when
   * that position's pool was too thin to rank against. Optional for the
   * same hand-built-row reason as `usage_trend` above. */
  overall_rating?: number | null;
}

export interface LeagueRankingsResponse {
  ok: true;
  players: RankedPlayer[];
}

/** One defender's IDP model value (GET .../idp/values): same 0-10,000 scale
 * as offensive values, but a model estimate, not a market price. */
export interface IdpValueRow {
  player_id: string;
  name: string;
  position: string;
  family: 'DL' | 'LB' | 'DB';
  team: string | null;
  age: number | null;
  injury_status: string | null;
  value: number;
  ppg: number;
  projected_points: number;
  points_over_replacement: number;
  confidence: 'high' | 'medium' | 'low';
  idp_rank: number;
}

/** `idp: false` (and no rows) for any league that does not start defenders. */
export interface LeagueIdpValuesResponse {
  ok: boolean;
  idp: boolean;
  players: IdpValueRow[];
  below_replacement_ids?: string[];
  unscored_keys?: string[];
  reason?: string;
  method?: string;
}

// player_id/name/position/team/age/status/injury_status/tier/score are the
// same shape as RankedPlayer, but position_rank/overall_rank here are
// wire-relative (rank among available free agents), not the league-global
// canonical_* rank /rankings returns — deliberately separate, matching
// services/mobile_api_service.py's get_league_waivers.
export interface WaiverPlayer {
  player_id: string;
  name: string | null;
  position: string | null;
  team: string | null;
  age: number | null;
  status: string | null;
  injury_status: string | null;
  tier: string | null;
  opportunity_label: string | null;
  score: number | null;
  position_rank: number | null;
  overall_rank: number | null;
  stale_free_agent: boolean;
  injury_replacement_fit: boolean;
  injury_replacement_note: string;
  // Sleeper's GLOBAL trending-add signal (modules.sleeper.trending_add_rank_map
  // / modules.waivers_ui.annotate_sleeper_trending_add on the backend) —
  // cross-league, last-24h add velocity across every league on Sleeper, NOT
  // scoped to this league. Deliberately distinct from this app's own
  // internal "usage trending up/down" role signal (see RankedPlayer's
  // usage_trend) — never present this as "trending in your league."
  sleeper_trending_add: boolean;
  // Sleeper's own 24h global add count when sleeper_trending_add is true;
  // null when not trending or the count is unavailable.
  sleeper_trending_add_count: number | null;
  // 1-indexed rank within Sleeper's global trending-add list (1 = most
  // added across all of Sleeper in the last 24h); null when not trending.
  sleeper_trending_add_rank: number | null;
  // This week's real NFL opponent (context only — never factored into
  // score/position_rank/overall_rank above). Null in the offseason/draft
  // or when the team code has no schedule match.
  opponent: string | null;
  opponent_is_home: boolean | null;
  /** Matchup-difficulty tier for this free agent's upcoming opponent AT
   * THEIR POSITION (modules.player_projections.
   * team_defense_points_allowed_by_position — the same signal/shape the
   * Matchup tab's weekly per-game projections already use, and the same
   * tier values Player Detail's Schedule tab shows as
   * ScheduleWeek.opponent_defense_tier). Context only, same "never
   * overweighted" contract as opponent/opponent_is_home above — never
   * factored into score/position_rank/overall_rank. Null whenever there's
   * no opponent, no sampled data for that opponent/position, or too few
   * sampled games for a reliable tier. */
  opponent_defense_tier: 'tough' | 'average' | 'weak' | null;
  /** 0-99 "OVR" badge — percentiled against the full league-eligible pool
   * at this position (rostered players included), NOT the wire-relative
   * free-agent-only pool position_rank/overall_rank above use. Same
   * curve/gate as QuickViewStats.overall_rating; null when that position's
   * pool was too thin to rank against. */
  overall_rating: number | null;
}

export interface WaiverFaabGuidance {
  low_bid: number;
  high_bid: number;
  pct_low: number;
  pct_high: number;
  remaining: number | null;
  dollars_known: boolean;
  label: string;
  /** False in leagues that don't run FAAB (Sleeper settings.waiver_type
   * != 2): every dollar/percent field is zero and `why` carries the
   * waiver-claim guidance. Absent from older servers — treat as true. */
  applicable?: boolean;
  waiver_mode?: WaiverMode;
  /** Short evidence-backed explanation of the bid ("3 teams need a RB and
   * 2 of them have more FAAB than you"), or the claim guidance. */
  why?: string;
  reasons?: string[];
  /** How much real market data backed the bid; "low" means a wider range. */
  data_confidence?: "high" | "medium" | "low";
}

/** Sleeper settings.waiver_type: 2 = faab, 1 = reverse_standings, 0 = rolling. */
export type WaiverMode = "faab" | "rolling" | "reverse_standings" | "unknown";

export interface WaiverPriorityAdd extends WaiverPlayer {
  recommendation_label: string;
  recommendation_tone: string;
  /** Null-safe: clients must render a missing/non-applicable bid. */
  faab: WaiverFaabGuidance | null;
  /** Real need-fit/standout-value confidence for this recommendation
   * (High/Medium/Low — modules.waivers_ui.waiver_confidence_label), the
   * same already-computed signals that ranked it into Priority Adds. Same
   * confidence language Trade Hub's cards already use. */
  confidence_label: string;
  confidence_reason: string;
}

// Shared shape for every endpoint that gates part of its own response by
// Premium — see docs/paywall audit: this mirrors web's real (server-side)
// gates, not just a UI hint.
export interface EntitlementGateInfo {
  is_premium: boolean;
}

export interface WaiversResponse {
  ok: true;
  players: WaiverPlayer[];
  priority_adds: WaiverPriorityAdd[];
  needed_positions: string[];
  available_count?: number;
  avg_wire_score?: number;
  faab_remaining?: number | null;
  faab_initial?: number | null;
  /** Sleeper settings.waiver_type; faab_enabled false = no dollar bids. */
  waiver_mode?: WaiverMode;
  faab_enabled?: boolean;
  // Secondary waiver board (Stash Candidates / Watchlist Depth / FAAB
  // Shortlist) — empty for Free, populated for Premium. Matches web's
  // modules/waivers_ui.py Premium-only gate.
  stash_candidates: WaiverPlayer[];
  watchlist_candidates: WaiverPlayer[];
  faab_targets: WaiverPlayer[];
  entitlement: EntitlementGateInfo;
  reason: string;
}

// Matches modules/league_value_settings.py's VALUATION_LENS_TO_SCORE_FIELD keys.
export type ValuationLens = 'Dynasty' | 'Rebuild' | 'Non-Dynasty';

export interface NewsItem {
  title: string | null;
  link: string | null;
  source: string | null;
  summary: string | null;
  published_ts: number | null;
  event_type: string | null;
  speculative: boolean;
}

export interface NewsResponse {
  ok: true;
  items: NewsItem[];
}

export type RosterRelationship = 'starter' | 'bench' | 'taxi' | 'ir' | null;

export interface AlertItem extends NewsItem {
  alert_key: string;
  read: boolean;
  matched_player: string | null;
  matched_player_id: string | null;
  // Sourced from the same roster slice matched_player_id resolves against
  // — null whenever the matched name isn't resolvable against the current
  // roster (e.g. a name-matched player no longer rostered), never guessed.
  matched_player_position: string | null;
  matched_player_team: string | null;
  matched_player_tier: string | null;
  relevance_reason: string | null;
  roster_relationship: RosterRelationship;
}

export type AlertsReason =
  | ''
  | 'no_sleeper_username_linked'
  | 'sleeper_user_not_found'
  | 'not_a_member_of_league'
  | 'empty_roster'
  | 'no_player_data';

export interface AlertsResponse {
  ok: true;
  items: AlertItem[];
  reason: AlertsReason;
}

export type TeamStrategy =
  | 'contender'
  | 'fringe_contender'
  | 'retool'
  | 'rebuild'
  | 'tank';

export interface GmStanceResponse {
  ok: boolean;
  strategy: TeamStrategy;
  /** False when nothing has been chosen yet and `strategy` is just the
   * "retool" fallback — lets the UI nudge for a real pick instead of
   * treating the default as an explicit one. The POST reports it too, so
   * "Reset to Auto" (which clears the stored stance) can be told apart
   * from setting one; older API builds omit it on the POST. */
  is_set?: boolean;
}

// Labels for the underlying TeamStrategy value the age-curve math keys on.
// No longer its own rendered control (see GmStanceContext/GmStanceHeaderButton
// — GM Stance / Team Situation merge, product decision 2026-09-26): kept
// only so code that already has a TeamStrategy value can show its label.
export const TEAM_STRATEGY_OPTIONS: Array<{ value: TeamStrategy; label: string }> = [
  { value: 'contender', label: 'Contender' },
  { value: 'fringe_contender', label: 'Fringe Contender' },
  { value: 'retool', label: 'Retool' },
  { value: 'rebuild', label: 'Rebuild' },
  { value: 'tank', label: 'Tank' },
];

/**
 * Team Situation is now the single source of truth for BOTH: it still only
 * ever biases trade-idea rationale TEXT server-side
 * (modules.trade_ideas.apply_team_stance_framing) AND — via
 * TEAM_STANCE_TO_STRATEGY below, the client mirror of
 * modules.team_stance.team_strategy_for_stance — drives the real age-curve
 * valuation math (modules.trade_hub_engine.apply_strategy_age_curve) GM
 * Stance's own separate, now-retired storage used to drive. GM Stance's
 * five states are coarser-grained than these three, so "fringe_contender"
 * and "tank" are no longer independently reachable — see the backend
 * mapping's docstring for the full rationale.
 */
export type TeamStance = 'rebuilding' | 'competing' | 'balanced';

export const TEAM_STANCE_OPTIONS: Array<{ value: TeamStance; label: string; description: string }> = [
  { value: 'rebuilding', label: 'Rebuilding', description: 'Prioritize youth and future draft capital' },
  { value: 'competing', label: 'Competing', description: 'Prioritize immediate roster impact' },
  { value: 'balanced', label: 'Balanced', description: 'Keep both current value and future flexibility' },
];

export interface TeamStanceResponse {
  ok: boolean;
  stance: TeamStance | '';
  options?: TeamStance[];
  /** The real backend-computed value (modules.team_stance.team_strategy_for_stance)
   * — prefer this over deriving it client-side when it's present (older API
   * builds may omit it on the POST response). */
  strategy?: TeamStrategy;
}

// Client mirror of modules.team_stance.team_strategy_for_stance's mapping
// table (modules/team_stance.py's `_STANCE_TO_TEAM_STRATEGY`), kept ONLY for
// GmStanceContext.setStance's genuine optimistic local update — the UI must
// reflect the new strategy immediately, before api.setTeamStance's request
// round-trips (see GmStanceContext.tsx). Every other call site should prefer
// the real `strategy` field the backend's GET/POST /team-stance and GET
// /gm-stance responses already compute and return (TeamStanceResponse.strategy
// / GmStanceResponse.strategy) instead of deriving it here.
//
// This exact table is asserted, key-for-key, against
// modules.team_stance._STANCE_TO_TEAM_STRATEGY by
// tests/test_team_stance.py::test_stance_to_strategy_mapping_matches_the_mobile_client_mirror
// — if that Python test ever fails, this table (and DEFAULT_TEAM_STRATEGY
// below) must be updated to match the real backend mapping.
export const TEAM_STANCE_TO_STRATEGY: Record<TeamStance, TeamStrategy> = {
  competing: 'contender',
  balanced: 'retool',
  rebuilding: 'rebuild',
};
export const DEFAULT_TEAM_STRATEGY: TeamStrategy = 'retool';

export function teamStrategyForStance(stance: TeamStance | ''): TeamStrategy {
  return stance ? TEAM_STANCE_TO_STRATEGY[stance] : DEFAULT_TEAM_STRATEGY;
}

/**
 * GM Plan — a season-arc roadmap layer, additive on top of the Dashboard's
 * one-off "Next Move" tile. Conditioned on the declared Team Situation
 * stance above (NOT the separate GM Stance/team-strategy system). Every
 * item in a focus area traces to an already-computed signal server-side
 * (a real trade idea, a real rank) — see modules.gm_plan on the backend.
 */
export type GmPlanSeasonPhase =
  | 'early_season'
  | 'trade_deadline_approach'
  | 'post_deadline'
  | 'playoff_push'
  | 'offseason_adjacent';

export type GmPlanFocusStatus = 'signal_found' | 'no_signal';

export interface GmPlanRankItem {
  label: string;
  rank: number;
  total_teams: number | null;
  tied: boolean;
  source: string;
  relative_weak_spot?: boolean;
}

export interface GmPlanRecordItem {
  label: 'Record';
  wins: number | null;
  losses: number | null;
  ties: number | null;
  source: string;
}

// Same already-cached rest-of-season Monte Carlo simulation the standalone
// Playoff Odds screen renders (see PlayoffOddsTeam) — looked up for the
// caller's own roster and surfaced as a "Where You Stand" fact. Omitted
// entirely (not sent) when that simulation isn't ready yet for this league.
export interface GmPlanPlayoffOddsItem {
  label: 'Playoff Odds';
  playoff_probability: number;
  median_seed: number | null;
  clinched: boolean;
  eliminated: boolean;
  source: string;
}

export interface GmPlanTradeItem {
  /** Same give/get asset dicts Trade Hub cards carry (empty when the idea had no detail). */
  send_assets?: PresentationAsset[];
  receive_assets?: PresentationAsset[];
  trade_gain?: number | null;
  partner_team_name: string;
  my_player: string;
  their_player: string;
  /** Real player identity for both sides of the exchange (modules.gm_plan's
   * data-contract fix — previously only display-name strings reached here).
   * May be '' when the underlying asset is a draft pick, not a player. */
  my_player_id: string;
  their_player_id: string;
  /** The receive-side player's injury tag (modules.rankings.injury_display_label
   * — same vocabulary GmTarget.injury_display already uses), '' when healthy
   * or unknown. Never fabricated. */
  their_player_injury_display: string;
  rationale: string;
  trade_confidence_label: string;
  priority: number | null;
  source: string;
}

export interface GmPlanInjuryItem {
  label: 'Injury Exposure';
  /** modules.rankings.summarize_team_injuries' injury_impact_flag (falls
   * back to health_flag) — the same vocabulary the Dashboard's Team
   * Snapshot health_flag already uses. */
  health_flag: string;
  injured_starters: number;
  /** Active/starting positions with a significant injury and no healthy
   * bench cover (modules.trade_analyzer_fit.roster_injury_context's
   * injury_need_positions) — the exact gap the connectivity audit flagged
   * GM Plan as missing. */
  injury_need_positions: string[];
  summary: string;
  source: string;
}

export type GmPlanFocusItem =
  | GmPlanRankItem
  | GmPlanRecordItem
  | GmPlanPlayoffOddsItem
  | GmPlanTradeItem
  | GmPlanInjuryItem;

export interface GmPlanFocusArea {
  key: 'standing' | 'trade_opportunities' | 'roster_construction';
  title: string;
  framing?: string;
  status: GmPlanFocusStatus;
  items: GmPlanFocusItem[];
  watch_for: string;
}

export interface GmPlanResponse {
  ok: boolean;
  quiet: boolean;
  reason: string;
  season_phase?: GmPlanSeasonPhase;
  season_phase_label?: string;
  team_stance?: TeamStance | '';
  team_stance_label?: string;
  headline?: string;
  focus_areas: GmPlanFocusArea[];
  trade_window?: TradeWindow;
  /** Free callers get quiet: true with is_premium: false (GM Plan is Premium). */
  is_premium?: boolean;
  upsell?: { title?: string; body?: string } | null;
}

export interface TradeCounterAction {
  action: 'remove_from_send' | 'add_to_receive';
  player_id: string;
  asset_type: string;
  label: string;
}

export interface TradeVerdict {
  band: string;
  ui_verdict: 'ACCEPT' | 'DECLINE' | 'COUNTER' | 'FAIR' | 'IDEA';
  confidence: string;
  rationale: string;
  value_summary: string;
  roster_summary: string;
  strategy_summary: string;
  risk_summary: string;
  counter_guidance: string;
  fit_total: number;
  value_delta: number;
  // 'idea' is Trade Hub's own tone — a suggested idea nobody has proposed
  // or acted on yet, as opposed to Trade Analyzer's real accept/decline/
  // counter verdict on a trade the caller is actually considering. Never
  // map a Trade Hub idea onto accept/decline: nothing has been accepted
  // or declined, and the share card's headline says so directly.
  tone: 'accept' | 'counter' | 'decline' | 'fair' | 'idea';
  counter_action?: TradeCounterAction | null;
}

export type TradeAnalyzerReason =
  | ''
  | 'no_sleeper_username_linked'
  | 'sleeper_user_not_found'
  | 'not_a_member_of_league'
  | 'no_player_data'
  | 'empty_roster'
  | 'assets_not_found'
  | 'fit_unavailable';

export interface TradeAnalyzerResponse {
  ok: true;
  verdict: TradeVerdict | null;
  reason: TradeAnalyzerReason;
  /** Non-empty once the league's trade deadline has passed — the analyzer
   * stays usable for offseason planning, this just says so. */
  planning_note?: string;
  trade_window?: TradeWindow;
}

export interface DraftPickAsset {
  pick_id: string;
  label: string | null;
  score: number | null;
  season: number | null;
  round: number | null;
  original_roster_id: string;
  owner_roster_id: string;
  original_team_name: string | null;
  owner_team_name: string | null;
  pick_tier: string | null;
  projected_pick_range: string | null;
  /** Valuation breakdown, forwarded verbatim from the server's own pick
   * model (modules/trade_ideas._pick_value_components) — Pick Detail renders
   * these as-is and never re-derives or approximates a value client-side.
   * Optional because an older API build predates them. */
  tier_bucket?: string | null;
  base_score?: number | null;
  /** Draft years beyond the next class — 0 for this year's and next year's
   * picks, then 1, 2, ... The "harder the further out" axis. */
  years_out?: number | null;
  /** 0.88 ** years_out. */
  future_discount?: number | null;
  team_modifier?: number | null;
  format_multiplier?: number | null;
  class_strength_multiplier?: number | null;
  prospect_strength_multiplier?: number | null;
  slot_percentile?: number | null;
  projected_slot_percentile?: number | null;
  /** Round-slot distribution (early/mid/late), sums to 1. */
  early_probability?: number | null;
  mid_probability?: number | null;
  late_probability?: number | null;
  /** 0-1 — the probability mass on the most likely slot bucket. Falls as the
   * pick moves further into the future. */
  projection_confidence?: number | null;
  projection_source?: string | null;
  is_current_year_pick?: boolean | null;
}

export interface DraftPicksResponse {
  ok: true;
  picks: DraftPickAsset[];
  reason: string;
}

export type TradeOutcomeAnswer = 'yes' | 'no' | 'didnt_send' | 'still_pending';

export interface TradeOutcomeAssetSummary {
  name: string;
  position: string;
  /** Present only for tracked assets (players, never draft picks) shared
   * after the quiet Trade Outcomes result tracking landed. Absent on older
   * rows and on picks — both simply can't be evaluated by the result sweep. */
  player_id?: string;
  /** The value_score visible on screen at share time, under whichever lens
   * was active — the baseline the later result sweep compares against. */
  value_score?: number | null;
}

export interface TradeOutcomeSummary {
  partner_team_name: string;
  send: TradeOutcomeAssetSummary[];
  receive: TradeOutcomeAssetSummary[];
  value_edge_label: string;
  /** Evaluation lens active at share time (e.g. "Dynasty") — the result
   * sweep re-values under this same lens for an apples-to-apples compare. */
  valuation_lens?: string;
}

export interface PendingTradeOutcome {
  id: string;
  league_id: string;
  partner_team_name: string;
  trade_summary: TradeOutcomeSummary;
  shared_at: string;
}

export interface PendingTradeOutcomesResponse {
  ok: true;
  outcomes: PendingTradeOutcome[];
}

/** modules.trade_outcome_results's computed "did it work?" snapshot — only
 * ever present once a real signal exists; `verdict`/`verdict_label` are null
 * whenever status is 'insufficient_data', never a fabricated call. */
export interface TradeOutcomeResultSummary {
  status: 'ready' | 'insufficient_data';
  reason: string;
  verdict: 'worked_out' | 'didnt_pan_out' | 'mixed' | 'neutral' | null;
  verdict_label?: string;
  confidence?: 'low' | 'medium' | 'high';
  days_since_trade: number | null;
  production?: { net_points_ppr: number; avg_net_per_week: number; weeks_counted: number } | null;
  value?: { sent_delta_pct: number; received_delta_pct: number; net_delta_pct: number } | null;
}

/** One answered (non-pending) shared trade — powers the mobile Trade
 * History screen (More > Trade History), pull-based only. */
export interface PastTradeOutcome {
  id: string;
  league_id: string;
  partner_team_name: string;
  trade_summary: TradeOutcomeSummary;
  outcome: 'yes' | 'no' | 'didnt_send';
  shared_at: string;
  outcome_recorded_at: string | null;
  result_summary: TradeOutcomeResultSummary | null;
  result_computed_at: string | null;
}

export interface TradeOutcomeHistoryResponse {
  ok: true;
  outcomes: PastTradeOutcome[];
}

export interface RecapTradeAsset {
  kind: 'player' | 'pick';
  name: string;
  player_id?: string;
  position?: string;
  team?: string;
  label?: string;
  season?: string;
  round?: number;
}

export interface RecapValueLens {
  lens: string;
  label: string;
  note: string;
}

export interface RecapStory {
  story_type: string;
  title: string;
  summary: string;
  glyph: string;
  primary_team: string;
  secondary_team: string;
  // Roster ids the story centers on, when available (empty string when not
  // applicable — modules/league_recaps.py's `_roster_id_str` convention).
  // Used to make story cards tappable through to TeamRoster.
  primary_roster_id: string;
  secondary_roster_id: string;
  players: string[];
  metric_label: string;
  metric_value: string;
  history_week: number;
  confidence: string;
  source_event_ids?: string[];
  // Trade stories only (modules/league_recaps.py's _trade_story extra):
  // full, untruncated asset lists (with player_id) for the tap-through
  // trade detail view, plus the value-lens summary shown alongside it.
  left_assets?: RecapTradeAsset[];
  right_assets?: RecapTradeAsset[];
  value_lenses?: RecapValueLens[];
  editorial_label?: string;
  historical_value_available?: boolean;
}

export interface WeeklyRecap {
  recap_id: string;
  league_id: string;
  season: string;
  week: number;
  headline: string;
  stories: RecapStory[];
  incomplete: boolean;
  empty_reason: string;
}

export interface RecapResponse {
  ok: true;
  recap: WeeklyRecap | null;
  reason: '' | 'no_completed_week';
  max_completed_week: number;
}

export interface QuickViewStatItem {
  label: string;
  value: string;
  note: string;
  tone: string;
  /** Percentile rank (1-100) of this stat within the player's position group,
   * or null when the backend had too small an eligible pool to rank against
   * (see player_quick_view.PERCENTILE_MIN_POOL). */
  percentile?: number | null;
}

export interface QuickViewSeason {
  season: number | null;
  season_type: string;
  games: number | null;
  complete: boolean | null;
  label: string;
  key_stats: QuickViewStatItem[];
  fantasy: QuickViewStatItem[];
  efficiency: QuickViewStatItem[];
  usage: QuickViewStatItem[];
}

export interface QuickViewStats {
  seasons: QuickViewSeason[];
  college: QuickViewStatItem[];
  college_available: boolean;
  career_totals_available: boolean;
  position: string;
  /** 0-99 headline rating, NBA 2K "OVR" style: the player's value_score
   * percentile inside their position group, re-expressed on the scale
   * people read at a glance. Null when the position pool was too thin to
   * rank against — the same gate the per-stat percentiles use
   * (player_quick_view.PERCENTILE_MIN_POOL), so nothing renders rather than
   * a made-up number. */
  overall_rating: number | null;
  /** This position's dynasty prime-age window (derived from the same age
   * curve that already discounts every player's value — not a separately
   * invented projection) plus where this player's current age sits
   * relative to it. Null for an unrecognized position or missing age. */
  prime_window: { start_age: number; end_age: number; status: 'before' | 'in' | 'after' } | null;
}

export interface QuickViewBio {
  years_in_league: string;
  draft_capital: string;
  college: string;
  height: string;
  weight: string;
  bye_week: string;
  contract_status: string;
}

/**
 * The weekly-usage recency read the backend already computes for every
 * player (modules/rankings.py: compute_recency_features) and blends into
 * opportunity. The server decides whether it is trustworthy enough to show
 * at all — 4+ usable games and a >= 5% move — so the client never
 * re-derives or re-gates it: a non-null value is safe to render as-is, and
 * null simply means "no trend worth stating".
 *
 * `trend_pct` is signed (+18 / -12); `magnitude_pct` is the same number
 * unsigned, for copy that already carries the direction in words.
 */
export interface UsageTrend {
  direction: 'up' | 'down';
  trend: number;
  trend_pct: number;
  magnitude_pct: number;
  confidence: number;
  confidence_key: 'high' | 'moderate';
  confidence_label: string;
  sample_n: number;
  window: number;
  usage_rate: number | null;
  baseline_rate: number | null;
  arrow: string;
  tone: 'positive' | 'negative';
  label: string;
  summary: string;
  detail: string;
}

export interface QuickViewModel {
  market_score: number | null;
  opportunity_score: number | null;
  scarcity_score: number | null;
  role_score: number | null;
  age_score: number | null;
  age_score_label: string;
  opportunity_confidence: number | null;
  workload_trend: string | null;
  usage_trend: UsageTrend | null;
  // One real sentence naming this player's strongest/weakest composite
  // value-score inputs (percentile-based, see modules.player_quick_view.
  // decision_fit_narrative) — null when the position pool is too thin to
  // support a meaningful comparison.
  decision_fit_narrative: string | null;
  // Market/Opportunity/Scarcity/Role, each re-expressed on the same 0-99
  // "OVR ring" scale via modules.player_quick_view.sub_ratings — a
  // position-relative percentile run through the exact same
  // _overall_rating_from_percentile curve the headline overall_rating uses.
  // Null under the same thin-pool gate as every other percentile here.
  market_rating: number | null;
  opportunity_rating: number | null;
  scarcity_rating: number | null;
  role_rating: number | null;
  // Durability: injury_multiplier * non_injury_risk_multiplier scaled
  // directly onto the 0-99 range — not position-ranked (see sub_ratings'
  // docstring for why). Null only when neither multiplier is present.
  durability_rating: number | null;
}

export interface WeeklyStatPoint {
  week: number;
  fantasy_points_ppr: number | null;
  snap_share: number | null;
}

export interface WeeklyStatsResponse {
  ok: true;
  season: number;
  weeks: WeeklyStatPoint[];
}

export interface CareerKeyStat {
  label: string;
  value: string;
}

export interface CareerSeason {
  season: number;
  age: number | null;
  games: number | null;
  current_season: boolean;
  key_stats: CareerKeyStat[];
}

export interface CareerResponse {
  ok: true;
  seasons: CareerSeason[];
}

/**
 * One real NFL game for this player's team — opponent, home/away, and the
 * published Vegas market's own spread/total (see modules.nfl_schedule's
 * docstring). spread_line is from this team's own perspective (negative =
 * this team favored). Context only: never a scoring input anywhere in the
 * app, and both line fields are null once the market hasn't published that
 * far out yet — never estimated client-side.
 */
/**
 * A single-week fantasy-point projection from
 * modules.player_projections.project_player_week — the first real per-game
 * projection feed in this app (distinct from the season-long value/
 * opportunity score used everywhere else). `status` drives rendering:
 * anything other than `"ok"` means "no projection" and every numeric field
 * is null — never a fabricated number. Honest statuses: `"bye_week"`,
 * `"no_opponent"` / `"no_schedule_data"`, `"insufficient_player_data"`,
 * `"unsupported_position"` (K/DEF/IDP — no defense-by-position signal
 * exists for them), `"unknown_player"` / `"no_team"`.
 */
export interface PlayerWeekProjection {
  status:
    | 'ok'
    | 'bye_week'
    | 'no_opponent'
    | 'no_schedule_data'
    | 'insufficient_player_data'
    | 'unsupported_position'
    | 'unknown_player'
    | 'no_team';
  point_estimate: number | null;
  low: number | null;
  high: number | null;
  confidence: 'low' | 'medium' | 'high' | null;
  opponent: string | null;
}

export interface ScheduleWeek {
  week: number;
  opponent: string | null;
  is_home: boolean | null;
  spread_line: number | null;
  total_line: number | null;
  played: boolean;
  team_score: number | null;
  opponent_score: number | null;
  bye: boolean;
  /** Real points-allowed-based defense strength for this opponent — never
   * a scoring input, display only. Null when that team has no completed
   * games yet to rank it by. */
  opponent_defense_tier: 'tough' | 'average' | 'weak' | null;
  /** This week's per-game projection — null for an already-played week (the
   * final score above already answers it) or a bye (nothing to project).
   * See `PlayerWeekProjection`. */
  projection: PlayerWeekProjection | null;
}

export interface ScheduleResponse {
  ok: true;
  team: string | null;
  season?: number;
  weeks: ScheduleWeek[];
}

export interface QuickViewResponse {
  ok: true;
  stats: QuickViewStats | null;
  bio: QuickViewBio | null;
  model: QuickViewModel | null;
  /** Server-resolved identity (valued row, else Sleeper's directory). */
  identity?: QuickViewIdentity | null;
  reason: '' | 'not_found';
}

export interface QuickViewIdentity {
  player_id: string;
  name: string;
  team: string | null;
  position: string | null;
  age: number | null;
  status: string | null;
  value_score: number | null;
  overall_rating: number | null;
  value_note: string;
  /** Team bye week for the current season; null for a free agent or no schedule. */
  bye_week?: number | null;
  /** True only in season, during that bye week. */
  on_bye_this_week?: boolean;
}

export interface PlayerAward {
  badge_id: string;
  category: string;
  /** modules/player_awards.py's PlayerBadge.family, e.g. "workhorse",
   * "bellcow", "targets", "pass-yards" — drives the per-award icon in
   * AwardsStrip, mirroring the web app's _accolade_kind/_accolade_emblem_svg
   * special-casing (modules/player_quick_view.py). */
  family: string;
  title: string;
  short_label: string;
  tier: 'gold' | 'silver' | 'bronze' | null;
  season: number | null;
  rank: number | null;
  metric_value: number | null;
  description: string;
  occurrence_count: number;
}

export interface PlayerAwardsResponse {
  ok: true;
  awards: PlayerAward[];
  reason: '' | 'not_found';
}

export interface GmTarget {
  player_id: string;
  source_surface: string;
  created_at: string | null;
  untouchable: boolean;
}

export interface GmTargetsResponse {
  ok: true;
  targets: GmTarget[];
}

export type GmTargetMutationReason = '' | 'at_cap' | 'not_available' | 'not_found';

export interface GmTargetMutationResponse {
  ok: boolean;
  reason: GmTargetMutationReason;
  cap?: number;
}

export interface PushMutationResponse {
  ok: boolean;
  reason: string;
  sent?: number;
}

// -----------------------------------------------------------------------
// College Football Prospect Scouting — crowdsourced shared signal (every
// signed-in user grades the same prospect pool; the aggregate feeds
// draft-class strength) + a personal watchlist layered on top. See
// modules/college_scouting.py and docs/supabase_college_scouting.sql.
// -----------------------------------------------------------------------

export interface ProspectScoutingAggregate {
  /** null when nobody has scouted this prospect yet — never a fabricated 0. */
  avg_grade: number | null;
  scout_count: number;
  avg_round_projection: number | null;
}

export interface MyScoutingReport {
  grade: number | null;
  round_projection: number | null;
  note: string;
}

export interface CollegeProspect {
  id: string;
  name: string;
  position: string;
  school: string;
  draft_year: number | null;
  aggregate: ProspectScoutingAggregate;
  my_report: MyScoutingReport | null;
  on_watchlist: boolean;
}

export interface CollegeProspectsResponse {
  ok: true;
  prospects: CollegeProspect[];
  // False when the real Supabase catalog isn't configured/migrated/
  // reachable yet. There is no fabricated-data fallback — `prospects` is
  // simply empty in that case, and the screen's existing "No prospects
  // yet" empty state covers it.
  catalog_available: boolean;
  reason: string;
}

export interface ScoutingMutationResponse {
  ok: boolean;
  reason: string;
}

// Mirrors modules/college_scouting.py's MIN_GRADE/MAX_GRADE/
// MIN_ROUND_PROJECTION/MAX_ROUND_PROJECTION exactly — the server is the
// real source of truth (422s outside this range), these just keep the
// grading UI's picker options in sync without a round trip.
export const MIN_GRADE = 1;
export const MAX_GRADE = 5;
export const MIN_ROUND_PROJECTION = 1;
export const MAX_ROUND_PROJECTION = 7;

// Matches modules/push_triggers.py's TOGGLEABLE_PUSH_CATEGORIES.
export type PushCategory = 'top_priority' | 'watch' | 'recap' | 'injury';

export interface PushPreferencesResponse {
  ok: boolean;
  categories: Record<PushCategory, boolean>;
}

export type UiDensityValue = 'guided' | 'compact';

export type ThemeModeValue = 'light' | 'dark' | 'auto';

export type ExperienceLevelValue = 'beginner' | 'advanced';

export interface DevicePreferencesResponse {
  ok: boolean;
  ui_density: UiDensityValue;
  theme_mode: ThemeModeValue;
  experience_level?: ExperienceLevelValue | null;
  last_league: { league_id: string; league_name: string } | null;
}

export type DashboardItemCategory = 'top_priority' | 'watch' | 'waiver_opportunity' | 'league_movement';

export interface DashboardTradePresentation {
  trade_package: TradePackage;
  trade_gain: number;
  trade_confidence_label: string;
  trade_market_realism_label: string;
  partner_team_name: string;
}

export interface DashboardItem {
  category: DashboardItemCategory;
  headline: string;
  reason: string;
  supporting_context: string;
  destination: string;
  route_player_id: string;
  route_player_name: string;
  /** Real player identity for a compact player module — sourced from the
   * same valued-player row the tile itself was built from
   * (modules.dashboard_engine). Empty string / null when this tile's
   * underlying row genuinely lacks the field (older tile shapes, or a pick
   * asset rather than a player) — never fabricated, so render nothing
   * rather than a placeholder. */
  route_player_position: string;
  route_player_team: string;
  route_player_tier: string;
  route_player_score: number | null;
  recommendation_narrative: Record<string, unknown> | null;
  presentation: DashboardTradePresentation | null;
  recommendation_id: string;
  /** Real tier word for a Next Move priority-ladder tile (e.g. "Priority" /
   * "Urgent" / "Watch" / "Opportunity" — modules.dashboard_engine's
   * NEED_TIER_LABELS). Empty string for every other tile (trade/waiver/etc.)
   * — never a fabricated confidence score. */
  tier_label: string;
}

export interface InjuryImpactPlayer {
  player_id: string;
  name: string;
  position: string;
  team: string;
  /** Same canonical stored tier every other player-identity surface reads
   * (e.g. RankedPlayer.tier) — empty string when this roster row has no
   * tier on file, never a fabricated one. */
  tier: string;
  /** Sleeper's raw status string (e.g. "Questionable"/"Out"). */
  injury_status: string;
  /** The engine's severity word (e.g. "major"/"moderate") — see PresentationAsset. */
  injury_level: string;
  /** "starter" / "weekly" / "depth" / "future asset" — how the player is used. */
  roster_relevance: string;
  /** "current" / "recent" / "aging" / "stale" / "update unknown". */
  freshness_label: string;
  player_value_score: number | null;
  impact_contribution: number | null;
}

export interface TeamSnapshot {
  wins: number | null;
  losses: number | null;
  ties: number | null;
  health_flag: string;
  /** The "why" behind health_flag — the same already-computed fields web
   * renders as its "Key injuries:" caption and injury impact note. */
  key_injuries_summary: string;
  top_injury_impact_summary: string;
  top_injury_impact_players: InjuryImpactPlayer[];
  /** The real total driving health_flag — top_injury_impact_players above
   * is trimmed to a couple of cards, so its .length undercounts. */
  injured_starters: number | null;
  average_age: number | null;
  power_rank: number | null;
  power_rank_tied: boolean;
  franchise_rank: number | null;
  franchise_rank_tied: boolean;
  starter_rank?: number | null;
  starter_rank_tied?: boolean;
  bench_rank?: number | null;
  bench_rank_tied?: boolean;
}

export interface DashboardEntitlementInfo extends EntitlementGateInfo {
  visible_count: number;
  hidden_count: number;
}

export interface DashboardResponse {
  ok: true;
  items: DashboardItem[];
  quiet: boolean;
  quiet_reason?: string;
  team_snapshot: TeamSnapshot | null;
  entitlement?: DashboardEntitlementInfo;
  reason: string;
}

/**
 * "Guess the Player" mini-game (coridian_, 2026-10-19: "on the app it would
 * be a pop-up") — mirrors web-next's GuessThePlayer* types (web-next/src/
 * lib/api.ts) exactly, since both clients hit the same GET /v1/guess-the-
 * player / POST /v1/guess-the-player/answer (services/mobile_api_service.py).
 * See modules/guess_the_player.py's module docstring for the real selection
 * spec. `stat_line` only ever holds real per-week fields this app tracks
 * (targets/receptions/rush or pass attempts) — never a fabricated yards/TD
 * figure.
 */
export interface GuessThePlayerStatLineItem {
  label: string;
  value: number;
}

export interface GuessThePlayerOption {
  player_id: string;
  name: string;
}

export interface GuessThePlayerPrompt {
  pick_id: string;
  season: number;
  week: number;
  position: string;
  /** Raw stored tier string (e.g. "depth") — same shape PlayerAvatar/
   * resolvePlayerTier already normalize everywhere else, so the ring can
   * render even before the reveal. */
  tier: string;
  stat_line: GuessThePlayerStatLineItem[];
  fantasy_points_ppr: number;
  options: GuessThePlayerOption[];
}

export interface GuessThePlayerStreak {
  current_streak: number;
  best_streak: number;
}

export interface GuessThePlayerCorrectIdentity {
  player_id: string;
  name: string;
  team: string;
  position: string;
  tier: string;
}

export interface GuessThePlayerResponse {
  ok: boolean;
  available: boolean;
  reason: string;
  prompt: GuessThePlayerPrompt | null;
  already_answered: boolean;
  last_result: 'correct' | 'incorrect' | null;
  /** Only ever populated when `already_answered` is true — never sent
   * alongside an unanswered prompt (that would leak the answer). */
  correct_player: GuessThePlayerCorrectIdentity | null;
  streak: GuessThePlayerStreak;
}

export interface GuessThePlayerAnswerResponse {
  ok: boolean;
  already_answered: boolean;
  correct: boolean;
  correct_player: GuessThePlayerCorrectIdentity;
  streak: GuessThePlayerStreak;
}

/**
 * "Who is who?" name-match mode — a SECOND, distinct daily mini-game
 * (coridian_, 2026-10-19, same Discord thread as Guess the Player above):
 * "you get two players and one player is, you know, a known name that's
 * good, and then one player is kind of an unknown name who maybe has
 * better stats than the known name, and so you pick and choose who is
 * who." Unlike Guess the Player, BOTH players' real identity is shown up
 * front — what's hidden is which of the two real, unlabeled stat lines
 * ("Slot A"/"Slot B") belongs to which player. Mirrors web-next's own
 * GuessThePlayerNameMatch* types exactly, since both clients hit the same
 * GET /v1/guess-the-player/name-match / POST
 * /v1/guess-the-player/name-match/answer. Its own daily pick and its own
 * persisted streak — never mixed with GuessThePlayerStreak above.
 */
export interface GuessThePlayerNameMatchIdentity {
  player_id: string;
  name: string;
  team: string;
  position: string;
  tier: string;
}

export interface GuessThePlayerNameMatchSlot {
  stat_line: GuessThePlayerStatLineItem[];
  fantasy_points_ppr: number;
}

export interface GuessThePlayerNameMatchPrompt {
  pick_id: string;
  season: number;
  week: number;
  famous_player: GuessThePlayerNameMatchIdentity;
  obscure_player: GuessThePlayerNameMatchIdentity;
  /** Keyed "A"/"B" — deliberately doesn't say which player each slot
   * belongs to; that's the guess. */
  slots: Record<string, GuessThePlayerNameMatchSlot>;
}

export interface GuessThePlayerNameMatchStreak {
  current_streak: number;
  best_streak: number;
}

export interface GuessThePlayerNameMatchCorrectPairing {
  famous_slot: string;
  obscure_slot: string;
}

export interface GuessThePlayerNameMatchResponse {
  ok: boolean;
  available: boolean;
  reason: string;
  prompt: GuessThePlayerNameMatchPrompt | null;
  already_answered: boolean;
  last_result: 'correct' | 'incorrect' | null;
  /** Only ever populated when `already_answered` is true — never sent
   * alongside an unanswered prompt (that would leak the pairing). */
  correct_pairing: GuessThePlayerNameMatchCorrectPairing | null;
  streak: GuessThePlayerNameMatchStreak;
}

export interface GuessThePlayerNameMatchAnswerResponse {
  ok: boolean;
  already_answered: boolean;
  correct: boolean;
  correct_pairing: GuessThePlayerNameMatchCorrectPairing;
  streak: GuessThePlayerNameMatchStreak;
}

/** The single highest-value-score player on a saved league's roster — the
 * top row of modules.dashboard_engine.build_league_summary's already-
 * computed roster_df, no new valuation math. Lean on purpose (not a full
 * RankedPlayer): just enough for the Portfolio share card's "standout
 * asset" avatar + name + score line. */
export interface PortfolioTopAsset {
  player_id: string;
  name: string | null;
  position: string | null;
  team: string | null;
  tier: string | null;
  score: number | null;
}

/**
 * One saved league's row on the cross-league Portfolio screen — the exact
 * same per-league summary GET /v1/leagues/{id}/dashboard already builds
 * (modules.dashboard_engine.build_league_summary), condensed to what a
 * compact row needs. `top_item` is that league's single highest-priority
 * Next Move tile (same shape as DashboardItem) — "the one thing to do in
 * this league right now." `top_items` is the same already-ranked/deduped
 * signal list `top_item` is just the first entry of (a few short lines at
 * most — a roster player's value trending down, an injury, a live news
 * story, actionable waiver info — whichever of those are genuinely true for
 * this team right now, never padded to a fixed count), for the quick-glance
 * multi-line card coridian_ asked for instead of a single headline.
 * `franchise_rank`/`roster_value_rank` and `archetype`/`archetype_label`
 * come from the same cached modules.league_rankings rankings frame
 * `power_rank` already reads, run through
 * modules.team_eval.refine_team_directions — the identical, already-cached
 * pass GET /v1/leagues/{id}/team-rankings uses for its own archetype column.
 */
export interface PortfolioLeague {
  league_id: string;
  league_name: string;
  team_name: string;
  wins: number | null;
  losses: number | null;
  ties: number | null;
  health_flag: string;
  power_rank: number | null;
  power_rank_tied: boolean;
  franchise_rank: number | null;
  franchise_rank_tied: boolean;
  roster_value_rank: number | null;
  roster_value_rank_tied: boolean;
  archetype: string | null;
  archetype_label: string | null;
  top_asset: PortfolioTopAsset | null;
  top_item: DashboardItem | null;
  top_items: DashboardItem[];
}

/** A saved league whose summary couldn't be built this time — Portfolio
 * shows every league that DID succeed rather than blanking the whole
 * screen over one broken league. */
export interface PortfolioFailedLeague {
  league_id: string;
  league_name: string;
  reason: string;
}

export interface PortfolioUpsell {
  title: string;
  body: string;
}

export interface PortfolioResponse {
  ok: true;
  is_premium: boolean;
  lens: string;
  leagues: PortfolioLeague[];
  failed_leagues: PortfolioFailedLeague[];
  /** Present only for a Free caller — Portfolio needs more than the one
   * league Free accounts can save, so Free gets this honest upsell instead
   * of an empty or broken screen. */
  upsell: PortfolioUpsell | null;
}

/** One saved league as listed by GET /v1/portfolio/leagues — just enough to
 * hold its place with a skeleton row and request that league's own row. */
export interface PortfolioSavedLeague {
  league_id: string;
  league_name: string;
}

/** GET /v1/portfolio/leagues — Portfolio's cheap index (Premium gate + the
 * caller's saved leagues, no per-league valuation work). `leagues`/
 * `failed_leagues` are always empty here; each league's row comes from
 * getPortfolioLeague. */
export interface PortfolioIndexResponse extends PortfolioResponse {
  saved_leagues: PortfolioSavedLeague[];
  reason?: string;
}

/** One player across the caller's leagues (GET /v1/portfolio/exposure). */
export interface PortfolioExposurePlayer {
  player_id: string;
  name: string;
  position: string;
  team: string;
  leagues_owned: number;
  league_names: string[];
  leagues: Array<{ league_id: string; league_name: string; value: number }>;
  share_of_leagues: number;
  value: number;
  share_of_value: number;
}

export interface PortfolioExposure {
  league_count: number;
  player_count: number;
  total_value: number;
  players: PortfolioExposurePlayer[];
  by_position: Array<{ position: string; value: number; share_of_value: number; roster_spots: number }>;
  concentration: {
    top_n: number;
    top_share_of_value: number;
    top_players: Array<{ player_id: string; name: string; value: number }>;
  };
}

/** GET /v1/portfolio/exposure (Pro). A Free caller gets `upsell` and no
 * `exposure`. ESPN leagues, and any that can't be read, are in `skipped_leagues`. */
export interface PortfolioExposureResponse {
  ok: boolean;
  is_premium: boolean;
  lens: string;
  exposure: PortfolioExposure | null;
  skipped_leagues: PortfolioFailedLeague[];
  upsell: { title: string; body: string } | null;
  reason?: string;
}

/** GET /v1/portfolio/leagues/{leagueId} — one saved league's Portfolio row.
 * Exactly one of `league` / `failed_league` is set for a Premium caller. */
export interface PortfolioLeagueResponse {
  ok: true;
  is_premium: boolean;
  lens: string;
  league: PortfolioLeague | null;
  failed_league: PortfolioFailedLeague | null;
  upsell: PortfolioUpsell | null;
}

export interface PresentationAsset {
  asset_type: 'player' | 'pick';
  label?: string;
  player_id?: string;
  name?: string;
  position?: string;
  team?: string;
  age?: number | null;
  score?: number | null;
  role?: string;
  injury_status?: string;
  // A short severity word (e.g. "minor"/"significant") — separate from
  // injury_status, which is Sleeper's raw status string (e.g. "Questionable").
  injury_level?: string;
  opportunity_explanation?: string;
  tier?: string;
  // 0-99 "OVR" badge alongside the tier ring's color — see
  // modules.trade_hub_engine.generate_trade_idea_records' comment for how
  // it's computed. Null when the pool was too thin to rank, same contract
  // as every other overall_rating field (OverallRatingBadge renders
  // nothing for null).
  overall_rating?: number | null;
  season?: string;
  round?: string;
  pick_no?: number;
  projected_range?: string;
  // Pick identity/valuation fields — present when asset_type is 'pick',
  // mirroring DraftPickAsset so a trade idea's pick can open the same
  // PickDetailScreen the Draft Center and Trade Analyzer picker use.
  pick_id?: string;
  original_roster_id?: string;
  owner_roster_id?: string;
  original_team_name?: string;
  owner_team_name?: string;
  pick_tier?: string;
  tier_bucket?: string;
  base_score?: number | null;
  years_out?: number | null;
  future_discount?: number | null;
  team_modifier?: number | null;
  format_multiplier?: number | null;
  class_strength_multiplier?: number | null;
  prospect_strength_multiplier?: number | null;
  slot_percentile?: number | null;
  projected_slot_percentile?: number | null;
  early_probability?: number | null;
  mid_probability?: number | null;
  late_probability?: number | null;
  projection_confidence?: number | null;
  projection_source?: string | null;
  is_current_year_pick?: boolean | null;
}

export interface TradePackage {
  send: PresentationAsset[];
  receive: PresentationAsset[];
  // Signed value-delta string (e.g. "+150"/"-800") and the confidence label,
  // computed server-side alongside send/receive — already shipping in the
  // response, just wasn't declared here before.
  value_edge: string;
  confidence: string;
}

export interface TradeIdea {
  partner_team_name: string;
  partner_team_avatar_url: string | null;
  /** Real untruncated per-side value totals (same fields web reads). */
  send_score?: number;
  receive_score?: number;
  // Real archetype label (e.g. "Rebuilding", "Aging Contender") from the
  // same computation /v1/leagues/{id}/team-rankings uses — empty when it
  // couldn't be matched to a roster.
  partner_team_archetype_label: string;
  // Real buy/sell pattern from this partner's actual Sleeper trade history
  // (modules.team_trade_history) — "Seller"/"Buyer"/"Neutral". Context
  // only; doesn't change trade_gain, confidence_label, or category.
  partner_trade_tendency: string;
  rationale: string;
  trade_gain: number;
  confidence_label: string;
  market_realism_label: string;
  reasoning_tags: string[];
  package: TradePackage;
  // "Headline Recommendation" for the top-ranked idea, otherwise one of
  // High Confidence / Need-Based / Contender / Rebuild / Draft Capital /
  // Age Optimization / Health Relief — matches web's Trade Hub categories.
  category: string;
  // Favorable / Fair / Slight Overpay / Major Overpay — a presentation
  // bucket derived from trade_gain, not a new/different number.
  value_edge_band: string;
  // "high_impact" (High confidence), "buy_low" (receiving a player whose
  // real opportunity_label reads Backup With Upside/Committee Back —
  // role trending up, price probably hasn't caught up), "sell_high"
  // (sending a Starter At Risk — established value, opportunity already
  // softening), or "" — real signals already on the idea, not new scoring.
  impact_tag: string;
  // player_ids from package.receive that are on the caller's GM Targets
  // watchlist — lets the card call out "lands your target" without a
  // second lookup, since package.receive already has the matching name.
  landed_gm_target_player_ids: string[];
  // All Trades only: which roster this idea was generated for (not
  // necessarily the caller's own), and that roster's real team name so a
  // card can read "Team A <-> Team B" instead of just naming the partner.
  // Both absent on regular Trade Hub ideas (always the caller's own).
  source_roster_id?: string;
  source_team_name?: string;
}

export interface TradeHubEntitlement {
  is_premium: boolean;
  approved_count: number;
  visible_count: number;
  hidden_count: number;
  free_limit: number;
  ad_bonus_per_unlock: number;
  max_ad_unlocks: number;
  ad_unlocks_applied: number;
}

export interface TradeHubResponse {
  ok: true;
  ideas: TradeIdea[];
  reason: string;
  entitlement?: TradeHubEntitlement;
  /** reason === 'trade_deadline_passed' carries this user-facing copy. */
  message?: string;
  trade_window?: TradeWindow;
}

export interface AllTradesEntitlement {
  is_premium: boolean;
  free_limit: number;
  ad_bonus_per_unlock: number;
  max_ad_unlocks: number;
  ad_unlocks_applied: number;
  // Free-only ideas remaining after this page, carried forward via
  // shownCount on the next "Load More" call.
  remaining_free: number;
}

export interface AllTradesResponse {
  ok: true;
  ideas: TradeIdea[];
  has_more: boolean;
  next_cursor: number;
  total_teams: number;
  entitlement: AllTradesEntitlement;
}

// Matches the backend's MAX_PLAYER_IDS_PER_REQUEST — batch client-side so a
// large roster/league fetch can't silently exceed it.
const MAX_PLAYER_IDS_PER_REQUEST = 300;

export const api = {
  /**
   * Arms/disarms showcase-mode masking of every response this client
   * returns. Called by ShowcaseModeProvider — nothing else should touch it.
   */
  setShowcaseModeEnabled,
  getMe: () => authorizedFetch<MeResponse>('/v1/me'),
  /** GDPR/CCPA data-access request — every row this account owns, as JSON. */
  exportMyData: () => authorizedFetch<{ ok: true; generated_at: string; user: object; tables: object }>('/v1/me/export'),
  getLeague: (leagueId: string) =>
    authorizedFetch<LeagueResponse>(`/v1/leagues/${encodeURIComponent(leagueId)}`),
  getLeagueUsers: (leagueId: string) =>
    authorizedFetch<LeagueUsersResponse>(
      `/v1/leagues/${encodeURIComponent(leagueId)}/users`,
    ),
  getLeagueRosters: (leagueId: string) =>
    authorizedFetch<LeagueRostersResponse>(
      `/v1/leagues/${encodeURIComponent(leagueId)}/rosters`,
    ),
  getLeagueTeamProfiles: (leagueId: string) =>
    authorizedFetch<LeagueTeamProfilesResponse>(
      `/v1/leagues/${encodeURIComponent(leagueId)}/team-profiles`,
    ),
  getLeagueTeamRankings: (leagueId: string) =>
    authorizedFetch<LeagueTeamRankingsResponse>(
      `/v1/leagues/${encodeURIComponent(leagueId)}/team-rankings`,
    ),
  getManagerTendencies: (leagueId: string) =>
    authorizedFetch<ManagerTendenciesSummaryResponse>(
      `/v1/leagues/${encodeURIComponent(leagueId)}/managers/tendencies`,
    ),
  getManagerTendencyDetail: (leagueId: string, rosterId: string | number) =>
    authorizedFetch<ManagerTendenciesDetailResponse>(
      `/v1/leagues/${encodeURIComponent(leagueId)}/managers/${encodeURIComponent(String(rosterId))}/tendencies`,
    ),
  getLeaguePlayoffOdds: (leagueId: string, options?: { lens?: ValuationLens }) => {
    const params = new URLSearchParams();
    if (options?.lens) params.set('lens', options.lens);
    const query = params.toString();
    return authorizedFetch<PlayoffOddsResponse>(
      `/v1/leagues/${encodeURIComponent(leagueId)}/playoff-odds${query ? `?${query}` : ''}`,
    );
  },
  getMyRoster: (leagueId: string) =>
    authorizedFetch<MyRosterResponse>(`/v1/leagues/${encodeURIComponent(leagueId)}/my-roster`),
  getLeagueDraftCenter: (leagueId: string, options?: { lens?: ValuationLens }) => {
    const params = new URLSearchParams();
    if (options?.lens) params.set('lens', options.lens);
    const query = params.toString();
    return authorizedFetch<DraftCenterResponse>(
      `/v1/leagues/${encodeURIComponent(leagueId)}/draft-center${query ? `?${query}` : ''}`,
    );
  },
  getLeagueMyTeam: (leagueId: string, options?: { lens?: ValuationLens }) => {
    const params = new URLSearchParams();
    if (options?.lens) params.set('lens', options.lens);
    const query = params.toString();
    return authorizedFetch<MyTeamResponse>(
      `/v1/leagues/${encodeURIComponent(leagueId)}/my-team${query ? `?${query}` : ''}`,
    );
  },
  getLeagueMyTeamNeeds: (leagueId: string, options?: { lens?: ValuationLens }) => {
    const params = new URLSearchParams();
    if (options?.lens) params.set('lens', options.lens);
    const query = params.toString();
    return authorizedFetch<MyTeamNeedsResponse>(
      `/v1/leagues/${encodeURIComponent(leagueId)}/my-team-needs${query ? `?${query}` : ''}`,
    );
  },
  getLeagueKeepers: (leagueId: string, options?: { lens?: ValuationLens }) => {
    const params = new URLSearchParams();
    if (options?.lens) params.set('lens', options.lens);
    const query = params.toString();
    return authorizedFetch<KeepersResponse>(
      `/v1/leagues/${encodeURIComponent(leagueId)}/keepers${query ? `?${query}` : ''}`,
    );
  },
  getLeagueMatchup: (leagueId: string, options?: { lens?: ValuationLens }) => {
    const params = new URLSearchParams();
    if (options?.lens) params.set('lens', options.lens);
    const query = params.toString();
    return authorizedFetch<MatchupResponse>(
      `/v1/leagues/${encodeURIComponent(leagueId)}/matchup${query ? `?${query}` : ''}`,
    );
  },
  postMatchupWhatIf: (
    leagueId: string,
    body: { lineup: MatchupWhatIfSlot[]; edit_index?: number | null },
  ) => authorizedPost<MatchupWhatIfResponse>(`/v1/leagues/${encodeURIComponent(leagueId)}/matchup/what-if`, body),
  getLeagueIdpValues: (leagueId: string) =>
    authorizedFetch<LeagueIdpValuesResponse>(`/v1/leagues/${encodeURIComponent(leagueId)}/idp/values`),
  getLeagueRankings: (leagueId: string, options?: { lens?: ValuationLens; limit?: number }) => {
    const params = new URLSearchParams();
    if (options?.lens) params.set('lens', options.lens);
    params.set('limit', String(options?.limit ?? 300));
    return authorizedFetch<LeagueRankingsResponse>(
      `/v1/leagues/${encodeURIComponent(leagueId)}/rankings?${params.toString()}`,
    );
  },
  getPlayerRankInLeague: (leagueId: string, playerId: string, options?: { lens?: ValuationLens }) => {
    const params = new URLSearchParams();
    if (options?.lens) params.set('lens', options.lens);
    const query = params.toString();
    return authorizedFetch<{ ok: true; player: RankedPlayer | null }>(
      `/v1/leagues/${encodeURIComponent(leagueId)}/players/${encodeURIComponent(playerId)}/rank${query ? `?${query}` : ''}`,
    );
  },
  getLeagueWaivers: (leagueId: string, options?: { lens?: ValuationLens; limit?: number }) => {
    const params = new URLSearchParams();
    if (options?.lens) params.set('lens', options.lens);
    if (options?.limit) params.set('limit', String(options.limit));
    return authorizedFetch<WaiversResponse>(
      `/v1/leagues/${encodeURIComponent(leagueId)}/waivers?${params.toString()}`,
    );
  },
  getNews: (limit = 30) => authorizedFetch<NewsResponse>(`/v1/news?limit=${limit}`),
  getPlayerNews: (playerId: string, limit = 5) =>
    authorizedFetch<NewsResponse>(`/v1/players/${encodeURIComponent(playerId)}/news?limit=${limit}`),
  getLeagueRecap: (leagueId: string, options?: { week?: number }) => {
    const params = new URLSearchParams();
    if (options?.week != null) params.set('week', String(options.week));
    const query = params.toString();
    return authorizedFetch<RecapResponse>(
      `/v1/leagues/${encodeURIComponent(leagueId)}/recap${query ? `?${query}` : ''}`,
    );
  },
  getLeagueDashboard: (leagueId: string) =>
    authorizedFetch<DashboardResponse>(`/v1/leagues/${encodeURIComponent(leagueId)}/dashboard`),
  // "Guess the Player" mini-game (coridian_, 2026-10-19) — league-
  // independent, one shared daily pick for every signed-in user, so it
  // doesn't take a leagueId the way getLeagueDashboard does.
  getGuessThePlayer: () => authorizedFetch<GuessThePlayerResponse>('/v1/guess-the-player'),
  answerGuessThePlayer: (pickId: string, playerId: string) =>
    authorizedPost<GuessThePlayerAnswerResponse>('/v1/guess-the-player/answer', {
      pick_id: pickId,
      player_id: playerId,
    }),
  // "Who is who?" name-match mini-game (coridian_, 2026-10-19) — a second,
  // distinct daily mini-game alongside Guess the Player above, with its
  // own daily pick and its own streak.
  getGuessThePlayerNameMatch: () =>
    authorizedFetch<GuessThePlayerNameMatchResponse>('/v1/guess-the-player/name-match'),
  answerGuessThePlayerNameMatch: (pickId: string, famousSlot: string) =>
    authorizedPost<GuessThePlayerNameMatchAnswerResponse>('/v1/guess-the-player/name-match/answer', {
      pick_id: pickId,
      famous_slot: famousSlot,
    }),
  /** Cross-league Portfolio — one row per saved league (Premium). */
  getPortfolio: () => authorizedFetch<PortfolioResponse>('/v1/portfolio'),
  /** Progressive Portfolio: the cheap index first, then one request per
   * saved league (fired concurrently) so each row paints as soon as its own
   * summary is ready instead of after the slowest league's. */
  getPortfolioIndex: () => authorizedFetch<PortfolioIndexResponse>('/v1/portfolio/leagues'),
  /** Player exposure across saved leagues (Pro). */
  getPortfolioExposure: () => authorizedFetch<PortfolioExposureResponse>('/v1/portfolio/exposure'),
  getPortfolioLeague: (leagueId: string) =>
    authorizedFetch<PortfolioLeagueResponse>(`/v1/portfolio/leagues/${encodeURIComponent(leagueId)}`),
  /** "All leagues at a glance" cards for the My Leagues screen (Premium).
   * Server-cached per league for a few minutes (cache_ttl_seconds). */
  getLeaguesGlance: () => authorizedFetch<LeaguesGlanceResponse>('/v1/leagues-glance'),
  /** `strategy='auto'` lets the server resolve the declared team stance
   * (same mapping as GET /team-stance), so no stance round trip is needed. */
  getTradeHubIdeas: (
    leagueId: string,
    strategy: TeamStrategy | 'auto' = 'retool',
    adUnlocks = 0,
    lens: ValuationLens = 'Dynasty',
  ) =>
    authorizedFetch<TradeHubResponse>(
      `/v1/leagues/${encodeURIComponent(leagueId)}/trade-hub?strategy=${strategy}&ad_unlocks=${adUnlocks}&lens=${encodeURIComponent(lens)}`,
    ),
  /** Trade Finder — "select these specific players, find who'd want them."
   * Same card shape as Trade Hub (no entitlement gating on this response;
   * this is a fresh, on-demand search rather than the passive board). */
  getTradeFinderIdeas: (
    leagueId: string,
    playerIds: string[],
    strategy: TeamStrategy = 'retool',
    lens: ValuationLens = 'Dynasty',
    /** Draft picks: `pickIds` are the caller's own DraftPickAsset.pick_id
     * values to offer (a picks-only selection is valid); `returnPicks` keeps
     * only packages that bring a partner pick back. */
    options: { pickIds?: string[]; returnPicks?: boolean } = {},
  ) =>
    authorizedFetch<TradeHubResponse>(
      `/v1/leagues/${encodeURIComponent(leagueId)}/trade-finder?player_ids=${encodeURIComponent(playerIds.join(','))}&strategy=${strategy}&lens=${encodeURIComponent(lens)}${options.pickIds && options.pickIds.length > 0 ? `&pick_ids=${encodeURIComponent(options.pickIds.join(','))}` : ''}${options.returnPicks ? '&return_picks=true' : ''}`,
    ),
  getAllTrades: (
    leagueId: string,
    options: {
      strategy?: TeamStrategy;
      lens?: ValuationLens;
      cursor?: number;
      pageSize?: number;
      shownCount?: number;
      adUnlocks?: number;
    } = {},
  ) => {
    const params = new URLSearchParams({
      strategy: options.strategy ?? 'retool',
      lens: options.lens ?? 'Dynasty',
      cursor: String(options.cursor ?? 0),
      page_size: String(options.pageSize ?? 3),
      shown_count: String(options.shownCount ?? 0),
      ad_unlocks: String(options.adUnlocks ?? 0),
    });
    return authorizedFetch<AllTradesResponse>(
      `/v1/leagues/${encodeURIComponent(leagueId)}/all-trades?${params.toString()}`,
    );
  },
  getLeagueAlerts: (leagueId: string, limit = 12) =>
    authorizedFetch<AlertsResponse>(`/v1/leagues/${encodeURIComponent(leagueId)}/alerts?limit=${limit}`),
  getPlayerQuickView: (playerId: string) =>
    authorizedFetch<QuickViewResponse>(`/v1/players/${encodeURIComponent(playerId)}/quick-view`),
  getPercentileExplorer: (playerId: string, stat: string, pool: 'position' | 'all') =>
    authorizedFetch<PercentileExplorerResponse>(
      `/v1/players/${encodeURIComponent(playerId)}/percentile-explorer?stat=${encodeURIComponent(stat)}&pool=${pool}`,
    ),
  getPlayerAwards: (playerId: string) =>
    authorizedFetch<PlayerAwardsResponse>(`/v1/players/${encodeURIComponent(playerId)}/awards`),
  getPlayerWeeklyStats: (playerId: string, season?: number) => {
    const query = season != null ? `?season=${encodeURIComponent(String(season))}` : '';
    return authorizedFetch<WeeklyStatsResponse>(`/v1/players/${encodeURIComponent(playerId)}/weekly-stats${query}`);
  },
  getPlayerCareer: (playerId: string) =>
    authorizedFetch<CareerResponse>(`/v1/players/${encodeURIComponent(playerId)}/career`),
  getPlayerSchedule: (playerId: string) =>
    authorizedFetch<ScheduleResponse>(`/v1/players/${encodeURIComponent(playerId)}/schedule`),
  lookupSleeperLeagues: (username: string) => {
    const query = username ? `?username=${encodeURIComponent(username)}` : '';
    return authorizedFetch<SleeperLeagueLookupResponse>(`/v1/sleeper/leagues${query}`);
  },
  // Cap-enforced server-side (free vs. premium) — check `reason === 'at_cap'`
  // and route to the paywall rather than treating it as a failure.
  saveLeague: (input: {
    leagueId: string;
    sleeperUsername?: string;
    leagueName?: string;
    makeDefault?: boolean;
    /** ESPN leagues only: the team the user picked as theirs. */
    rosterId?: string;
  }) =>
    authorizedPost<SaveLeagueResponse>('/v1/leagues/save', {
      league_id: input.leagueId,
      sleeper_username: input.sleeperUsername ?? '',
      league_name: input.leagueName ?? '',
      make_default: input.makeDefault ?? false,
      roster_id: input.rosterId ?? '',
    }),
  getLeagueWarmupStatus: (leagueId: string) =>
    authorizedFetch<import('./leagueWarmup').WarmupStatus>(
      `/v1/leagues/${encodeURIComponent(leagueId)}/warmup-status`,
    ),
  previewEspnLeague: (leagueId: string, season: number) =>
    authorizedPost<EspnLeaguePreviewResponse>('/v1/espn/leagues/preview', { league_id: leagueId, season }),
  getGmTargets: (leagueId: string) =>
    authorizedFetch<GmTargetsResponse>(`/v1/leagues/${encodeURIComponent(leagueId)}/gm-targets`),
  addGmTarget: (leagueId: string, playerId: string, sourceSurface = 'gm_targets') =>
    authorizedPost<GmTargetMutationResponse>(`/v1/leagues/${encodeURIComponent(leagueId)}/gm-targets`, {
      player_id: playerId,
      source_surface: sourceSurface,
    }),
  removeGmTarget: (leagueId: string, playerId: string) =>
    authorizedDelete<GmTargetMutationResponse>(
      `/v1/leagues/${encodeURIComponent(leagueId)}/gm-targets/${encodeURIComponent(playerId)}`,
    ),
  setGmTargetUntouchable: (leagueId: string, playerId: string, untouchable: boolean) =>
    authorizedPatch<GmTargetMutationResponse>(
      `/v1/leagues/${encodeURIComponent(leagueId)}/gm-targets/${encodeURIComponent(playerId)}/untouchable`,
      { untouchable },
    ),
  getCollegeProspects: () => authorizedFetch<CollegeProspectsResponse>('/v1/scouting/prospects'),
  submitScoutingReport: (
    prospectId: string,
    body: { grade: number; round_projection?: number | null; note?: string },
  ) =>
    authorizedPost<ScoutingMutationResponse>(
      `/v1/scouting/prospects/${encodeURIComponent(prospectId)}/report`,
      body,
    ),
  deleteScoutingReport: (prospectId: string) =>
    authorizedDelete<ScoutingMutationResponse>(
      `/v1/scouting/prospects/${encodeURIComponent(prospectId)}/report`,
    ),
  addProspectToWatchlist: (prospectId: string) =>
    authorizedPost<ScoutingMutationResponse>(
      `/v1/scouting/watchlist/${encodeURIComponent(prospectId)}`,
      {},
    ),
  removeProspectFromWatchlist: (prospectId: string) =>
    authorizedDelete<ScoutingMutationResponse>(
      `/v1/scouting/watchlist/${encodeURIComponent(prospectId)}`,
    ),
  getTeamStance: (leagueId: string) =>
    authorizedFetch<TeamStanceResponse>(`/v1/leagues/${encodeURIComponent(leagueId)}/team-stance`),
  setTeamStance: (leagueId: string, stance: TeamStance) =>
    authorizedPost<TeamStanceResponse>(`/v1/leagues/${encodeURIComponent(leagueId)}/team-stance`, { stance }),
  getGmPlan: (leagueId: string, options?: { lens?: ValuationLens }) => {
    const params = new URLSearchParams();
    if (options?.lens) params.set('lens', options.lens);
    const query = params.toString();
    return authorizedFetch<GmPlanResponse>(
      `/v1/leagues/${encodeURIComponent(leagueId)}/gm-plan${query ? `?${query}` : ''}`,
    );
  },
  registerPushToken: (expoPushToken: string, platform: string, deviceName = '') =>
    authorizedPost<PushMutationResponse>('/v1/push/register', {
      expo_push_token: expoPushToken,
      platform,
      device_name: deviceName,
    }),
  unregisterPushToken: (expoPushToken: string) =>
    authorizedPost<PushMutationResponse>('/v1/push/unregister', {
      expo_push_token: expoPushToken,
    }),
  sendTestPush: () => authorizedPost<PushMutationResponse>('/v1/push/test', {}),
  getPushPreferences: () => authorizedFetch<PushPreferencesResponse>('/v1/push/preferences'),
  updatePushPreference: (category: PushCategory, enabled: boolean) =>
    authorizedPost<PushPreferencesResponse>('/v1/push/preferences', { category, enabled }),
  getDevicePreferences: () => authorizedFetch<DevicePreferencesResponse>('/v1/preferences'),
  /** Set by the onboarding carousel's last step, same call as web-next's
   * OnboardingCarousel (`api.setExperienceLevel`). */
  setExperienceLevel: (level: ExperienceLevelValue) =>
    authorizedPost<DevicePreferencesResponse>('/v1/preferences', { experience_level: level }),
  updateDevicePreferences: (body: {
    uiDensity?: UiDensityValue;
    themeMode?: ThemeModeValue;
    lastLeagueId?: string;
    lastLeagueName?: string;
  }) =>
    authorizedPost<DevicePreferencesResponse>('/v1/preferences', {
      ui_density: body.uiDensity,
      theme_mode: body.themeMode,
      last_league_id: body.lastLeagueId,
      last_league_name: body.lastLeagueName,
    }),
  markAlertRead: (leagueId: string, alertKey: string) =>
    authorizedPost<{ ok: boolean; reason: string }>(
      `/v1/leagues/${encodeURIComponent(leagueId)}/alerts/read`,
      { alert_key: alertKey },
    ),
  /** Deprecated (GM Stance / Team Situation merge, product decision
   * 2026-09-26) — kept only for a pre-merge build still calling it. Current
   * code reads Team Situation directly via getTeamStance/setTeamStance and
   * derives `strategy` client-side via teamStrategyForStance. */
  getGmStance: (leagueId: string) =>
    authorizedFetch<GmStanceResponse>(`/v1/leagues/${encodeURIComponent(leagueId)}/gm-stance`),
  /** Deprecated, see getGmStance above. `null` is a no-op server-side now —
   * Team Situation has no "unset" concept. */
  updateGmStance: (leagueId: string, strategy: TeamStrategy | null) =>
    authorizedPost<GmStanceResponse>(`/v1/leagues/${encodeURIComponent(leagueId)}/gm-stance`, { strategy }),
  postTradeAnalyzer: (
    leagueId: string,
    body: {
      sendPlayerIds: string[];
      receivePlayerIds: string[];
      sendPickIds?: string[];
      receivePickIds?: string[];
      strategy?: TeamStrategy;
      lens?: ValuationLens;
      partnerRosterId?: string;
    },
  ) =>
    authorizedPost<TradeAnalyzerResponse>(`/v1/leagues/${encodeURIComponent(leagueId)}/trade-analyzer`, {
      send_player_ids: body.sendPlayerIds,
      receive_player_ids: body.receivePlayerIds,
      send_pick_ids: body.sendPickIds ?? [],
      receive_pick_ids: body.receivePickIds ?? [],
      strategy: body.strategy ?? 'retool',
      lens: body.lens ?? 'Dynasty',
      partner_roster_id: body.partnerRosterId ?? '',
    }),
  getLeagueDraftPicks: (leagueId: string, options?: { lens?: ValuationLens }) => {
    const params = new URLSearchParams();
    if (options?.lens) params.set('lens', options.lens);
    const query = params.toString();
    return authorizedFetch<DraftPicksResponse>(
      `/v1/leagues/${encodeURIComponent(leagueId)}/draft-picks${query ? `?${query}` : ''}`,
    );
  },
  getPlayers: async (playerIds: string[]): Promise<Record<string, PlayerSummary>> => {
    const uniqueIds = [...new Set(playerIds.filter(Boolean))];
    if (uniqueIds.length === 0) return {};

    const batches: string[][] = [];
    for (let i = 0; i < uniqueIds.length; i += MAX_PLAYER_IDS_PER_REQUEST) {
      batches.push(uniqueIds.slice(i, i + MAX_PLAYER_IDS_PER_REQUEST));
    }

    const results = await Promise.all(
      batches.map((batch) =>
        authorizedFetch<PlayersResponse>(`/v1/players?ids=${batch.join(',')}`),
      ),
    );

    return results.reduce<Record<string, PlayerSummary>>((acc, result) => {
      Object.assign(acc, result.players);
      return acc;
    }, {});
  },
  recordTradeShare: (
    leagueId: string,
    body: {
      partnerTeamName?: string;
      send: Array<{ name: string; position: string; player_id?: string; value_score?: number | null }>;
      receive: Array<{ name: string; position: string; player_id?: string; value_score?: number | null }>;
      valueEdgeLabel?: string;
      valuationLens?: string;
    },
  ) =>
    authorizedPost<{ ok: boolean; reason: string }>(
      `/v1/leagues/${encodeURIComponent(leagueId)}/trade-outcomes`,
      {
        partner_team_name: body.partnerTeamName ?? '',
        send: body.send,
        receive: body.receive,
        value_edge_label: body.valueEdgeLabel ?? '',
        valuation_lens: body.valuationLens ?? '',
      },
    ),
  getPendingTradeOutcomes: () => authorizedFetch<PendingTradeOutcomesResponse>('/v1/trade-outcomes/pending'),
  getTradeOutcomeHistory: () => authorizedFetch<TradeOutcomeHistoryResponse>('/v1/trade-outcomes/history'),
  answerTradeOutcome: (outcomeId: string, outcome: TradeOutcomeAnswer) =>
    authorizedPost<{ ok: boolean; reason: string }>(
      `/v1/trade-outcomes/${encodeURIComponent(outcomeId)}/answer`,
      { outcome },
    ),
};
