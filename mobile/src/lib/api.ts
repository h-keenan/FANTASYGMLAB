import { supabase } from './supabase';
import { env } from './env';

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
  init?: { method?: 'GET' | 'POST' | 'DELETE'; jsonBody?: unknown },
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

  return body as T;
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
  tier: string | null;
  score: number | null;
  slot: string | null;
  suggested_starter: boolean;
  opportunity_label: string | null;
}

export interface MyTeamResponse {
  ok: true;
  starters: LineupPlayer[];
  bench: LineupPlayer[];
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
   * treating the default as an explicit one. Absent on the POST response,
   * where a successful update is always an explicit choice. */
  is_set?: boolean;
}

// Shared across every screen with a strategy picker (Trade Hub, Trade
// Analyzer, League Detail's GM Stance card) so the options/labels can
// never drift between them.
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
  ui_verdict: 'ACCEPT' | 'DECLINE' | 'COUNTER' | 'FAIR';
  confidence: string;
  rationale: string;
  value_summary: string;
  roster_summary: string;
  strategy_summary: string;
  risk_summary: string;
  counter_guidance: string;
  fit_total: number;
  value_delta: number;
  tone: 'accept' | 'counter' | 'decline' | 'fair';
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

export interface QuickViewModel {
  market_score: number | null;
  opportunity_score: number | null;
  scarcity_score: number | null;
  role_score: number | null;
  age_score: number | null;
  age_score_label: string;
  opportunity_confidence: number | null;
  workload_trend: string | null;
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
}

export interface GmTargetsResponse {
  ok: true;
  targets: GmTarget[];
}

export type GmTargetMutationReason = '' | 'at_cap' | 'not_available';

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

export interface DevicePreferencesResponse {
  ok: boolean;
  ui_density: UiDensityValue;
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
  recommendation_narrative: Record<string, unknown> | null;
  presentation: DashboardTradePresentation | null;
  recommendation_id: string;
}

export interface TeamSnapshot {
  wins: number | null;
  losses: number | null;
  ties: number | null;
  health_flag: string;
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

// Matches the backend's MAX_PLAYER_IDS_PER_REQUEST — batch client-side so a
// large roster/league fetch can't silently exceed it.
const MAX_PLAYER_IDS_PER_REQUEST = 300;

export const api = {
  getMe: () => authorizedFetch<MeResponse>('/v1/me'),
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
  getTradeHubIdeas: (leagueId: string, strategy: TeamStrategy = 'retool', adUnlocks = 0) =>
    authorizedFetch<TradeHubResponse>(
      `/v1/leagues/${encodeURIComponent(leagueId)}/trade-hub?strategy=${strategy}&ad_unlocks=${adUnlocks}`,
    ),
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
    lastLeagueId?: string;
    lastLeagueName?: string;
  }) =>
    authorizedPost<DevicePreferencesResponse>('/v1/preferences', {
      ui_density: body.uiDensity,
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
  updateGmStance: (leagueId: string, strategy: TeamStrategy) =>
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
