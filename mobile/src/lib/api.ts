import { supabase } from './supabase';
import { env } from './env';
import { maskShowcaseFields, setShowcaseModeEnabled } from './showcaseMode';

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

async function authorizedRequest<T>(
  path: string,
  init?: { method?: 'GET' | 'POST' | 'PATCH' | 'DELETE'; jsonBody?: unknown },
): Promise<T> {
  const { data, error: sessionError } = await supabase.auth.getSession();
  if (sessionError || !data.session) {
    throw new ApiError(401, 'Not signed in.');
  }

  const response = await fetch(`${env.apiBaseUrl}${path}`, {
    method: init?.method ?? 'GET',
    headers: {
      Authorization: `Bearer ${data.session.access_token}`,
      ...(init?.jsonBody !== undefined ? { 'Content-Type': 'application/json' } : {}),
    },
    ...(init?.jsonBody !== undefined ? { body: JSON.stringify(init.jsonBody) } : {}),
  });

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

export type SaveLeagueReason = '' | 'at_cap' | 'league_not_found' | 'not_available';

export interface SaveLeagueResponse {
  ok: boolean;
  reason: SaveLeagueReason;
  // How many leagues this account's plan may keep (see MeResponse.league_cap).
  cap: number;
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
  franchise_rank: number | null;
  draft_capital_rank: number | null;
  starter_rank: number | null;
  bench_rank: number | null;
  age_rank: number | null;
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
}

export interface LeagueTeamRankingsResponse {
  ok: true;
  teams: TeamRanking[];
  reason: string;
}

export interface DraftPosture {
  label: string;
  note: string;
  tone: string;
  draft_capital_rank: number | null;
  draft_capital: number | null;
  future_draft_capital_rank: number | null;
  future_draft_capital: number | null;
  strategy_display: string | null;
  power_rank: number | null;
  franchise_rank: number | null;
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
}

export interface MyTeamResponse {
  ok: true;
  starters: LineupPlayer[];
  bench: LineupPlayer[];
  reason: string;
  roster_id?: string;
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

export interface MatchupResponse {
  ok: true;
  /** Sleeper's current week (league settings.leg) — null when the league hasn't started one. */
  week: number | null;
  my_team: MatchupSide | null;
  opponent: MatchupSide | null;
  comparison: MatchupComparison | null;
  basis: 'season_value';
  basis_label: string;
  reason: string;
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
  // This week's real NFL opponent (context only — never factored into
  // score/position_rank/overall_rank above). Null in the offseason/draft
  // or when the team code has no schedule match.
  opponent: string | null;
  opponent_is_home: boolean | null;
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
}

export interface WaiverPriorityAdd extends WaiverPlayer {
  recommendation_label: string;
  recommendation_tone: string;
  faab: WaiverFaabGuidance;
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

// Single source for the stance options/labels. Rendered only by
// GmStanceHeaderButton now — the one stance control every screen shares.
export const TEAM_STRATEGY_OPTIONS: Array<{ value: TeamStrategy; label: string }> = [
  { value: 'contender', label: 'Contender' },
  { value: 'fringe_contender', label: 'Fringe Contender' },
  { value: 'retool', label: 'Retool' },
  { value: 'rebuild', label: 'Rebuild' },
  { value: 'tank', label: 'Tank' },
];

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
}

export interface TradeOutcomeSummary {
  partner_team_name: string;
  send: TradeOutcomeAssetSummary[];
  receive: TradeOutcomeAssetSummary[];
  value_edge_label: string;
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
  reason: '' | 'not_found';
}

export interface PlayerAward {
  badge_id: string;
  category: string;
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

// Matches modules/push_triggers.py's TOGGLEABLE_PUSH_CATEGORIES.
export type PushCategory = 'top_priority' | 'watch' | 'recap' | 'injury';

export interface PushPreferencesResponse {
  ok: boolean;
  categories: Record<PushCategory, boolean>;
}

export type UiDensityValue = 'guided' | 'compact';

export type ThemeModeValue = 'light' | 'dark' | 'auto';

export interface DevicePreferencesResponse {
  ok: boolean;
  ui_density: UiDensityValue;
  theme_mode: ThemeModeValue;
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
  recommendation_narrative: Record<string, unknown> | null;
  presentation: DashboardTradePresentation | null;
  recommendation_id: string;
}

export interface InjuryImpactPlayer {
  player_id: string;
  name: string;
  position: string;
  team: string;
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
  franchise_rank: number | null;
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
  getLeagueMatchup: (leagueId: string, options?: { lens?: ValuationLens }) => {
    const params = new URLSearchParams();
    if (options?.lens) params.set('lens', options.lens);
    const query = params.toString();
    return authorizedFetch<MatchupResponse>(
      `/v1/leagues/${encodeURIComponent(leagueId)}/matchup${query ? `?${query}` : ''}`,
    );
  },
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
  getTradeHubIdeas: (
    leagueId: string,
    strategy: TeamStrategy = 'retool',
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
  ) =>
    authorizedFetch<TradeHubResponse>(
      `/v1/leagues/${encodeURIComponent(leagueId)}/trade-finder?player_ids=${encodeURIComponent(playerIds.join(','))}&strategy=${strategy}&lens=${encodeURIComponent(lens)}`,
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
  }) =>
    authorizedPost<SaveLeagueResponse>('/v1/leagues/save', {
      league_id: input.leagueId,
      sleeper_username: input.sleeperUsername ?? '',
      league_name: input.leagueName ?? '',
      make_default: input.makeDefault ?? false,
    }),
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
  getGmStance: (leagueId: string) =>
    authorizedFetch<GmStanceResponse>(`/v1/leagues/${encodeURIComponent(leagueId)}/gm-stance`),
  /** Pass `null` to clear the stored stance ("Reset to Auto") — a later
   * getGmStance then reports is_set=false and the app is back on the
   * auto-picked default. */
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
      send: Array<{ name: string; position: string }>;
      receive: Array<{ name: string; position: string }>;
      valueEdgeLabel?: string;
    },
  ) =>
    authorizedPost<{ ok: boolean; reason: string }>(
      `/v1/leagues/${encodeURIComponent(leagueId)}/trade-outcomes`,
      {
        partner_team_name: body.partnerTeamName ?? '',
        send: body.send,
        receive: body.receive,
        value_edge_label: body.valueEdgeLabel ?? '',
      },
    ),
  getPendingTradeOutcomes: () => authorizedFetch<PendingTradeOutcomesResponse>('/v1/trade-outcomes/pending'),
  answerTradeOutcome: (outcomeId: string, outcome: TradeOutcomeAnswer) =>
    authorizedPost<{ ok: boolean; reason: string }>(
      `/v1/trade-outcomes/${encodeURIComponent(outcomeId)}/answer`,
      { outcome },
    ),
};
