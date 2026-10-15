import { env } from "./env";
import { supabase } from "./supabase";

/**
 * Client for services/mobile_api_service.py. Mirrors mobile/src/lib/api.ts's
 * authorizedRequest pattern: every call re-pulls the current Supabase
 * session (supabase-js's autoRefreshToken keeps it valid) and attaches it
 * as a Bearer header. No session, no request.
 */
export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

const REQUEST_TIMEOUT_MS = 30_000;

async function performRequest<T>(
  path: string,
  init: { method?: "GET" | "POST" | "PATCH" | "DELETE"; jsonBody?: unknown } | undefined,
  accessToken: string,
): Promise<T> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  let response: Response;
  try {
    response = await fetch(`${env.apiBaseUrl}${path}`, {
      method: init?.method ?? "GET",
      headers: {
        Authorization: `Bearer ${accessToken}`,
        ...(init?.jsonBody !== undefined ? { "Content-Type": "application/json" } : {}),
      },
      ...(init?.jsonBody !== undefined ? { body: JSON.stringify(init.jsonBody) } : {}),
      signal: controller.signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiError(0, "The request timed out. Check your connection and try again.");
    }
    throw new ApiError(0, "Could not reach the server. Check your connection and try again.");
  } finally {
    clearTimeout(timeoutId);
  }

  let body: unknown = null;
  try {
    body = await response.json();
  } catch {
    body = null;
  }

  if (!response.ok) {
    const detail =
      body && typeof body === "object" && "detail" in body
        ? String((body as { detail?: unknown }).detail ?? "")
        : "";
    throw new ApiError(response.status, detail || `Request failed with status ${response.status}.`);
  }

  return body as T;
}

async function authorizedRequest<T>(
  path: string,
  init?: { method?: "GET" | "POST" | "PATCH" | "DELETE"; jsonBody?: unknown },
): Promise<T> {
  const { data } = await supabase.auth.getSession();
  const accessToken = data.session?.access_token;
  if (!accessToken) {
    throw new ApiError(401, "Not signed in.");
  }
  return performRequest<T>(path, init, accessToken);
}

export interface MeResponse {
  ok: boolean;
  user: {
    id: string;
    email: string;
    entitlement: "free" | "premium";
    sleeper_username: string;
    profile_status: string;
    league_cap: number;
  };
  premium_benefits: string[];
}

export interface SleeperLeagueSummary {
  league_id: string;
  name: string;
  season: string;
  total_rosters: number;
}

export interface SleeperLeaguesResponse {
  ok: boolean;
  status: string;
  username: string;
  leagues: SleeperLeagueSummary[];
  message: string;
}

export interface SaveLeagueResponse {
  ok: boolean;
  reason: string;
  cap: number;
  league?: { league_id: string; league_name: string; is_default: boolean };
}

export interface MyRosterResponse {
  ok: boolean;
  roster: Record<string, unknown> | null;
  reason: string;
}

export interface BriefingItem {
  category: string;
  headline: string;
  reason: string;
  supporting_context: string | null;
  destination: string;
  route_player_id: string;
  route_player_name: string;
  route_player_position: string;
  route_player_team: string;
  route_player_tier: string;
  route_player_score: number | null;
  recommendation_narrative: string | null;
  presentation: Record<string, unknown> | null;
  recommendation_id: string;
  tier_label: string;
}

export interface TeamSnapshot {
  wins: number | null;
  losses: number | null;
  ties: number | null;
  health_flag: string;
  key_injuries_summary: string;
  top_injury_impact_summary: string;
  top_injury_impact_players: unknown[];
  injured_starters: number | null;
  average_age: number | null;
  power_rank: number | null;
  power_rank_tied: boolean;
  franchise_rank: number | null;
  franchise_rank_tied: boolean;
  starter_rank: number | null;
  starter_rank_tied: boolean;
  bench_rank: number | null;
  bench_rank_tied: boolean;
}

export interface DashboardResponse {
  ok: boolean;
  items: BriefingItem[];
  quiet: boolean;
  quiet_reason: string;
  team_snapshot: TeamSnapshot | null;
  reason: string;
  entitlement: { is_premium: boolean; visible_count: number; hidden_count: number };
}

/** One roster slot on My Team's Roster Core/Depth — mirrors mobile's
 * LineupPlayer (mobile/src/lib/api.ts), the reference implementation for
 * GET .../my-team. `overall_rating` is the 0-99 "OVR" badge, percentiled
 * against the full league-eligible pool at this position (see that
 * endpoint's docstring) — null when that position's pool was too thin to
 * rank against, in which case the circular gauge must not render at all,
 * never a fabricated value. */
export interface LineupPlayer {
  player_id: string;
  name: string | null;
  position: string | null;
  team: string | null;
  age: number | null;
  status: string | null;
  injury_status: string | null;
  injury_label: string;
  ruled_out: boolean;
  tier: string | null;
  score: number | null;
  slot: string | null;
  suggested_starter: boolean;
  roster_slot?: "starter" | "bench" | "ir" | "taxi";
  opportunity_label: string | null;
  overall_rating: number | null;
}

export interface MyTeamResponse {
  ok: boolean;
  starters: LineupPlayer[];
  bench: LineupPlayer[];
  reason: string;
  roster_id?: string;
}

/** One position room's need classification — GET .../my-team-needs'
 * `position_groups`, straight off modules.trade_analyzer_fit.
 * build_team_needs_assessment (see that endpoint's docstring). */
export interface PositionNeedGroup {
  position: string;
  classification: "covered" | "short_term_need" | "future_risk" | string;
  reasons: string[];
  upgrade_opportunity: boolean;
  temporary_injury_pressure: boolean;
}

export interface BiggestNeed {
  label: string;
  value: string;
  note: string;
}

export interface MyTeamNeedsResponse {
  ok: boolean;
  reason: string;
  show_franchise_construction: boolean;
  superflex: boolean;
  te_premium: boolean;
  /** League-relative position rooms (QB/RB/WR/TE) — My Team's Strength &
   * Pressure "Strength" card. */
  strengths: string[];
  /** Short-term-need rooms not already explained by a temporary injury —
   * the same "Pressure point" card. */
  weaknesses: string[];
  biggest_need: BiggestNeed | null;
  position_groups: PositionNeedGroup[];
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
  // Already-computed Standings-board presentation fields (modules.
  // league_standings.build_league_standings_bundle, via GET
  // .../team-rankings) — null until standings_available (see
  // LeagueTeamRankingsResponse.standings_available below).
  standing_rank: number | null;
  win_pct_label: string | null;
  points_for_label: string | null;
  points_against_label: string | null;
  playoff_status: string | null;
  on_playoff_line: boolean;
  power_rank: number | null;
  power_rank_tied: boolean;
  power_score: number | null;
  franchise_rank: number | null;
  franchise_rank_tied: boolean;
  franchise_score: number | null;
  draft_capital_rank: number | null;
  draft_capital_rank_tied: boolean;
  draft_capital_score: number | null;
  pick_count: number | null;
  first_rounders: number | null;
  starter_rank: number | null;
  starter_rank_tied: boolean;
  starter_score: number | null;
  bench_rank: number | null;
  bench_rank_tied: boolean;
  bench_score: number | null;
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
  trade_tendency: string;
  transaction_activity_count: number;
  firsts_acquired: number;
  firsts_sent: number;
  current_streak: number;
  team_badges: string[];
  injured_starters: number | null;
  /** Real, server-computed injury-impact label ("Stable" when nothing is
   * meaningfully affecting this roster) — modules.league_rankings.
   * build_roster_health_metrics_frame, the same source My Team's Team
   * Snapshot and Dashboard's Team Snapshot tile read. */
  health_flag: string | null;
}

export interface LeagueTeamRankingsResponse {
  ok: boolean;
  teams: TeamRanking[];
  reason: string;
  standings_available: boolean;
  standings_message: string;
  season: string;
  week_label: string;
  playoff_teams: number | null;
}

/** Real Monte-Carlo rest-of-season simulation result for one team —
 * mirrors mobile's PlayoffOddsTeam (mobile/src/lib/api.ts), the reference
 * client for GET .../playoff-odds. `clinched`/`eliminated` are only ever
 * true at exactly 100/0 — a structural property of the simulation. */
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
  ok: boolean;
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

/** One give/get asset inside a trade idea's package — mirrors mobile's
 * PresentationAsset (mobile/src/lib/api.ts), the same
 * modules.compact_fantasy_assets.presentation_asset shape GET .../trade-hub
 * already serializes. Only the fields the Trade Hub card actually renders
 * are declared here; the picker/valuation-detail fields mobile's
 * PickDetailScreen reads are left off since web-next has no pick-detail
 * screen yet. */
export interface TradeAsset {
  asset_type: "player" | "pick";
  player_id?: string;
  name?: string;
  position?: string;
  team?: string;
  age?: number | null;
  score?: number | null;
  role?: string;
  injury_status?: string;
  tier?: string;
  overall_rating?: number | null;
  label?: string;
  season?: string;
  round?: string;
  pick_no?: number;
  projected_range?: string;
  owner_team_name?: string;
}

export interface TradePackage {
  send: TradeAsset[];
  receive: TradeAsset[];
  value_edge: string;
  confidence: string;
}

/** One trade-idea card — mirrors mobile's TradeIdea (mobile/src/lib/api.ts),
 * the same modules.trade_hub_engine.TradeIdeaCard.to_dict() shape
 * GET .../trade-hub returns for both mobile and web. `send_score`/
 * `receive_score` are the real, untruncated per-side totals (added in
 * Revision 3 for this page's lean bar — see that endpoint's docstring). */
export interface TradeIdea {
  partner_team_name: string;
  partner_team_avatar_url?: string | null;
  partner_team_archetype_label?: string;
  partner_trade_tendency?: string;
  rationale: string;
  trade_gain: number;
  confidence_label: string;
  market_realism_label: string;
  reasoning_tags: string[];
  package: TradePackage;
  category: string;
  value_edge_band: string;
  impact_tag: string;
  landed_gm_target_player_ids: string[];
  send_score: number;
  receive_score: number;
}

export interface TradeHubEntitlement {
  is_premium: boolean;
  approved_count: number;
  visible_count: number;
  hidden_count: number;
  free_limit: number;
}

export interface TradeHubResponse {
  ok: boolean;
  ideas: TradeIdea[];
  reason: string;
  entitlement: TradeHubEntitlement | null;
}

// player_id/name/position/team/age/status/injury_status/tier/score mirror
// RankedPlayer, but position_rank/overall_rank here are wire-relative (rank
// among available free agents), not the league-global canonical_* rank
// /rankings returns — deliberately separate, matching
// services/mobile_api_service.py's get_league_waivers and mobile's own
// WaiverPlayer (mobile/src/lib/api.ts), the reference implementation for
// this endpoint.
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
  // Sleeper's GLOBAL trending-add signal — cross-league, last-24h add
  // velocity across every league on Sleeper, NOT scoped to this league. See
  // modules.waivers_ui.annotate_sleeper_trending_add.
  sleeper_trending_add: boolean;
  sleeper_trending_add_count: number | null;
  sleeper_trending_add_rank: number | null;
  // This week's real NFL opponent (context only — never factored into
  // score/position_rank/overall_rank). Null in the offseason/draft.
  opponent: string | null;
  opponent_is_home: boolean | null;
  opponent_defense_tier: "tough" | "average" | "weak" | null;
  /** 0-99 "OVR" badge, percentiled against the full league-eligible pool at
   * this position (rostered players included) — same curve/gate as
   * MyTeamResponse's LineupPlayer.overall_rating; null when that position's
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
  /** Real need-fit/standout-value confidence for this recommendation
   * (High/Medium/Low — modules.waivers_ui.waiver_confidence_label), the
   * same already-computed signals that ranked it into Priority Adds. */
  confidence_label: string;
  confidence_reason: string;
}

export interface WaiversResponse {
  ok: boolean;
  players: WaiverPlayer[];
  priority_adds: WaiverPriorityAdd[];
  needed_positions: string[];
  available_count?: number;
  avg_wire_score?: number;
  /** Already computed server-side for injury_replacement_fit's own filter
   * — see GET .../waivers' docstring. Optional: absent on the two early
   * "nothing to show" return paths (no player data / no free agents). */
  injured_starters?: number;
  injury_positions?: string[];
  // Secondary waiver board (Stash Candidates / Watchlist Depth / FAAB
  // Shortlist) — empty for Free, populated for Premium. Matches web's
  // modules/waivers_ui.py Premium-only gate.
  stash_candidates: WaiverPlayer[];
  watchlist_candidates: WaiverPlayer[];
  faab_targets: WaiverPlayer[];
  entitlement: { is_premium: boolean };
  reason: string;
}

/** This week's per-game projection (modules.player_projections.
 * project_player_week, trimmed server-side by _projection_summary_dict) —
 * mirrors mobile's PlayerWeekProjection (mobile/src/lib/api.ts), the
 * reference implementation for every endpoint that surfaces one. The
 * server deliberately omits `basis` (recency-weighted internals) before
 * this ever reaches a client, so this type only declares the fields that
 * are actually ever present on the wire. */
export interface PlayerWeekProjection {
  status:
    | "ok"
    | "bye_week"
    | "no_opponent"
    | "no_schedule_data"
    | "insufficient_player_data"
    | "unsupported_position"
    | "unknown_player"
    | "no_team";
  point_estimate: number | null;
  low: number | null;
  high: number | null;
  confidence: "low" | "medium" | "high" | null;
  opponent: string | null;
}

/**
 * A suggested starter on the weekly Matchup page — mirrors mobile's
 * MatchupStarter (mobile/src/lib/api.ts). `score` is the same season-long
 * value/opportunity signal the rest of the app uses, deliberately NOT a
 * weekly points projection (see SEASON_VALUE_BASIS_LABEL in
 * services/mobile_api_service.py) — `why` explains the suggestion in those
 * same season-form terms only.
 */
export interface MatchupStarter extends LineupPlayer {
  why: string;
}

/**
 * A player Sleeper reports as ACTUALLY starting this week for this roster —
 * real data, not a recommendation. Mirrors mobile's MatchupRealStarter.
 * `score` is still the season-value signal (identity/context only);
 * `actual_points` is this starter's real point total scored so far this
 * week (live during in-progress games, final once the week completes).
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
  actual_points: number | null;
  projection: PlayerWeekProjection | null;
  /** Whether THIS player's own NFL game has actually kicked off this week —
   * distinct from `MatchupSide.has_live_data`, which only means Sleeper has
   * locked the week's starters. A starter whose game hasn't started yet
   * still reports `actual_points === 0`, which is NOT a real score — gate
   * on this, never on `actual_points`, before treating 0 as genuine. Null
   * when the signal isn't available (no resolvable team, bye, schedule
   * fetch hiccup) — treat as unknown, never as "started". */
  game_started: boolean | null;
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
  starters_basis: "suggested_optimal_lineup";
  /** This roster's ACTUAL current-week lineup, straight from Sleeper's own
   * matchup payload — may differ from `starters` above. Empty when
   * `has_live_data` is false. */
  real_starters: MatchupRealStarter[];
  /** This roster's real point total for the week. Null when `has_live_data`
   * is false. */
  real_points: number | null;
  /** False when Sleeper hasn't populated a real lineup for this roster yet
   * this week (matchup not started / not locked). Render `real_starters`/
   * `real_points` ONLY when this is true — otherwise they're empty/null by
   * design, not a real 0. */
  has_live_data: boolean;
  real_starters_basis: "sleeper_actual_lineup";
}

export interface MatchupComparison {
  my_season_value: number;
  opponent_season_value: number;
  margin: number;
  edge: "you" | "opponent" | "even";
  headline: string;
  basis: "season_value";
  basis_label: string;
}

/** This week's REAL score comparison, from Sleeper's own live points. Null
 * until both sides have `has_live_data`. */
export interface MatchupRealComparison {
  my_points: number;
  opponent_points: number;
  margin: number;
  edge: "you" | "opponent" | "even";
  basis: "sleeper_actual_lineup";
  basis_label: string;
}

export interface MatchupResponse {
  ok: boolean;
  /** Sleeper's current week (league settings.leg) — null when the league
   * hasn't started one. */
  week: number | null;
  my_team: MatchupSide | null;
  opponent: MatchupSide | null;
  comparison: MatchupComparison | null;
  /** Real current-week score comparison — null when either side lacks live
   * data yet. */
  real_comparison: MatchupRealComparison | null;
  basis: "season_value";
  basis_label: string;
  reason: string;
}

export type RosterRelationship = "starter" | "bench" | "taxi" | "ir" | null;

/** One roster-relevant news item — mirrors mobile's AlertItem (mobile/src/
 * lib/api.ts), the reference implementation for GET .../alerts. That
 * endpoint's own docstring is explicit that this is "one league's feed,
 * not the web app's full Alerts notification system" (Streamlit's
 * modules/alerts_activity.py timeline, which also folds in the Dashboard-
 * style action-item inbox with its own trade_hub/waivers/my_team/rankings
 * destinations) — read state here is real, but there is no destination
 * routing to port: every item's only two CTAs are the source article link
 * and the matched player's identity, same as mobile's screen. */
export interface AlertItem {
  title: string | null;
  link: string | null;
  source: string | null;
  summary: string | null;
  published_ts: number | null;
  event_type: string | null;
  speculative: boolean;
  alert_key: string;
  read: boolean;
  matched_player: string | null;
  matched_player_id: string | null;
  // Sourced from the same roster slice matched_player_id resolves against —
  // null whenever the matched name isn't resolvable against the current
  // roster (e.g. a name-matched player no longer rostered), never guessed.
  matched_player_position: string | null;
  matched_player_team: string | null;
  matched_player_tier: string | null;
  relevance_reason: string | null;
  roster_relationship: RosterRelationship;
}

export type AlertsReason =
  | ""
  | "no_sleeper_username_linked"
  | "sleeper_user_not_found"
  | "not_a_member_of_league"
  | "empty_roster"
  | "no_player_data";

export interface AlertsResponse {
  ok: boolean;
  items: AlertItem[];
  reason: AlertsReason;
}

/** The single highest-value-score player on a saved league's roster —
 * mirrors mobile's PortfolioTopAsset (mobile/src/lib/api.ts). Lean on
 * purpose: just enough for a "standout asset" line, no new valuation math. */
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
 * same per-league summary GET .../dashboard already builds
 * (modules.dashboard_engine.build_league_summary), condensed to what a
 * compact card needs. `top_items` is the already-ranked/deduped "Next
 * Move" signal list (PORTFOLIO_MAX_SIGNALS = 3 — a roster player's value
 * trending down, an injury, a live news story, actionable waiver info,
 * whichever are genuinely true for this team right now), the same
 * BriefingItem shape Today's Game Plan's GamePlanCard already renders.
 * `top_item` is just that list's first entry, kept for callers that only
 * need the single headline. Mirrors mobile's PortfolioLeague exactly.
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
  top_item: BriefingItem | null;
  top_items: BriefingItem[];
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
  ok: boolean;
  is_premium: boolean;
  lens: string;
  leagues: PortfolioLeague[];
  failed_leagues: PortfolioFailedLeague[];
  /** Present only for a Free caller — Portfolio needs more than the one
   * league Free accounts can save, so Free gets this honest upsell instead
   * of an empty or broken screen. */
  upsell: PortfolioUpsell | null;
  reason?: string;
}

/** GM Plan — a season-arc roadmap: where the caller stands, their best
 * trade paths, and their roster construction, framed by their declared
 * Team Situation stance (modules.team_stance — Rebuilding/Competing/
 * Balanced; NOT the separate GM Stance/team-strategy system). Every item
 * traces to an already-computed signal server-side (see modules.gm_plan);
 * when a focus area has no real signal it says so honestly via
 * `watch_for` instead of inventing advice. Mirrors mobile's GmPlanResponse
 * (mobile/src/lib/api.ts) but declared fresh here rather than imported,
 * since this app's TradeAsset (below) already covers the give/get asset
 * shape GET .../gm-plan's trade items carry on send_assets/receive_assets
 * (modules.gm_plan's visual-identity fix, PR #1047) — mobile's own type
 * hasn't been updated to declare those fields yet, but the wire payload
 * already has them. */
export type GmPlanSeasonPhase =
  | "early_season"
  | "trade_deadline_approach"
  | "playoff_push"
  | "offseason_adjacent";

export type GmPlanFocusStatus = "signal_found" | "no_signal";

export interface GmPlanRankItem {
  label: string;
  rank: number;
  total_teams: number | null;
  tied: boolean;
  source: string;
  relative_weak_spot?: boolean;
}

export interface GmPlanRecordItem {
  label: "Record";
  wins: number | null;
  losses: number | null;
  ties: number | null;
  source: string;
}

/** Same already-cached rest-of-season Monte Carlo simulation the standalone
 * Playoff Odds screen renders (see PlayoffOddsTeam) — looked up for the
 * caller's own roster and surfaced as a "Where You Stand" fact. Omitted
 * entirely (not sent) when that simulation isn't ready yet for this league. */
export interface GmPlanPlayoffOddsItem {
  label: "Playoff Odds";
  playoff_probability: number;
  median_seed: number | null;
  clinched: boolean;
  eliminated: boolean;
  source: string;
}

/** modules.gm_plan._trade_focus_area's trade-opportunity item.
 * send_assets/receive_assets are the SAME raw TradeAsset dicts Trade Hub's
 * own cards render (modules.compact_fantasy_assets) — reused here rather
 * than re-derived, so this page can show real give/get player identity
 * (OvrGauge/PositionBadge) instead of name-only text. Both are empty
 * arrays (never missing) when the underlying idea carried no asset detail. */
export interface GmPlanTradeItem {
  partner_team_name: string;
  my_player: string;
  their_player: string;
  my_player_id: string;
  their_player_id: string;
  /** The receive-side player's injury tag (modules.rankings.
   * injury_display_label), '' when healthy or unknown. Never fabricated. */
  their_player_injury_display: string;
  rationale: string;
  trade_confidence_label: string;
  priority: number | null;
  send_assets: TradeAsset[];
  receive_assets: TradeAsset[];
  trade_gain: number | null;
  source: string;
}

/** One already-identified player inside a GmPlanInjuryItem —
 * modules.rankings.summarize_team_injuries' top_injury_impact_players,
 * capped to the positions actually driving injury_need_positions. */
export interface GmPlanInjuredPlayer {
  asset_type: "player";
  player_id: string;
  name: string;
  position: string;
  team: string;
  injury_status: string;
  player_tier: string;
}

/** The connectivity-audit fix's one new "Roster Construction" fact: a
 * significant injury at an active/starting roster spot with no healthy
 * bench cover. Only ever present when modules.gm_plan found real
 * uncovered exposure — never a fabricated "all clear". */
export interface GmPlanInjuryItem {
  label: "Injury Exposure";
  health_flag: string;
  injured_starters: number;
  injury_need_positions: string[];
  injured_players: GmPlanInjuredPlayer[];
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
  key: "standing" | "trade_opportunities" | "roster_construction";
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
  team_stance?: string;
  team_stance_label?: string;
  headline?: string;
  focus_areas: GmPlanFocusArea[];
}

export const api = {
  getMe: () => authorizedRequest<MeResponse>("/v1/me"),

  lookupSleeperLeagues: (username: string) =>
    authorizedRequest<SleeperLeaguesResponse>(
      `/v1/sleeper/leagues?username=${encodeURIComponent(username)}`,
    ),

  saveLeague: (input: { leagueId: string; sleeperUsername?: string; leagueName?: string; makeDefault?: boolean }) =>
    authorizedRequest<SaveLeagueResponse>("/v1/leagues/save", {
      method: "POST",
      jsonBody: {
        league_id: input.leagueId,
        sleeper_username: input.sleeperUsername ?? "",
        league_name: input.leagueName ?? "",
        make_default: input.makeDefault ?? false,
      },
    }),

  linkSleeperUsername: (sleeperUsername: string) =>
    authorizedRequest<{ ok: boolean; sleeper_username?: string; reason?: string }>("/v1/me/link-sleeper", {
      method: "POST",
      jsonBody: { sleeper_username: sleeperUsername },
    }),

  getMyRoster: (leagueId: string) =>
    authorizedRequest<MyRosterResponse>(`/v1/leagues/${encodeURIComponent(leagueId)}/my-roster`),

  getDashboard: (leagueId: string, lens: string = "Dynasty") =>
    authorizedRequest<DashboardResponse>(
      `/v1/leagues/${encodeURIComponent(leagueId)}/dashboard?lens=${encodeURIComponent(lens)}`,
    ),

  getMyTeam: (leagueId: string, lens: string = "Dynasty") =>
    authorizedRequest<MyTeamResponse>(
      `/v1/leagues/${encodeURIComponent(leagueId)}/my-team?lens=${encodeURIComponent(lens)}`,
    ),

  getMyTeamNeeds: (leagueId: string, lens: string = "Dynasty") =>
    authorizedRequest<MyTeamNeedsResponse>(
      `/v1/leagues/${encodeURIComponent(leagueId)}/my-team-needs?lens=${encodeURIComponent(lens)}`,
    ),

  getTeamRankings: (leagueId: string, lens: string = "Dynasty") =>
    authorizedRequest<LeagueTeamRankingsResponse>(
      `/v1/leagues/${encodeURIComponent(leagueId)}/team-rankings?lens=${encodeURIComponent(lens)}`,
    ),

  getLeaguePlayoffOdds: (leagueId: string, lens: string = "Dynasty") =>
    authorizedRequest<PlayoffOddsResponse>(
      `/v1/leagues/${encodeURIComponent(leagueId)}/playoff-odds?lens=${encodeURIComponent(lens)}`,
    ),

  // strategy/lens default to the same "retool"/"Dynasty" GET .../trade-hub
  // itself defaults to. `ad_unlocks` is a mobile-only reward mechanic (see
  // that endpoint's docstring) — web always passes 0.
  getTradeHub: (leagueId: string, strategy: string = "retool", lens: string = "Dynasty") =>
    authorizedRequest<TradeHubResponse>(
      `/v1/leagues/${encodeURIComponent(leagueId)}/trade-hub?strategy=${encodeURIComponent(strategy)}&lens=${encodeURIComponent(lens)}&ad_unlocks=0`,
    ),

  getLeagueWaivers: (leagueId: string, lens: string = "Dynasty", limit: number = 150) =>
    authorizedRequest<WaiversResponse>(
      `/v1/leagues/${encodeURIComponent(leagueId)}/waivers?lens=${encodeURIComponent(lens)}&limit=${limit}`,
    ),

  getLeagueMatchup: (leagueId: string, lens: string = "Dynasty") =>
    authorizedRequest<MatchupResponse>(
      `/v1/leagues/${encodeURIComponent(leagueId)}/matchup?lens=${encodeURIComponent(lens)}`,
    ),

  getLeagueAlerts: (leagueId: string, limit: number = 12) =>
    authorizedRequest<AlertsResponse>(
      `/v1/leagues/${encodeURIComponent(leagueId)}/alerts?limit=${limit}`,
    ),

  markAlertRead: (leagueId: string, alertKey: string) =>
    authorizedRequest<{ ok: boolean }>(
      `/v1/leagues/${encodeURIComponent(leagueId)}/alerts/read`,
      { method: "POST", jsonBody: { alert_key: alertKey } },
    ),

  // Cross-league "Portfolio" — one row per saved league, Premium-gated
  // (see PortfolioResponse's own docstring). No leagueId param: this spans
  // every saved league at once, unlike every other call above.
  getPortfolio: (lens: string = "Dynasty") =>
    authorizedRequest<PortfolioResponse>(`/v1/portfolio?lens=${encodeURIComponent(lens)}`),

  getGmPlan: (leagueId: string, lens: string = "Dynasty") =>
    authorizedRequest<GmPlanResponse>(
      `/v1/leagues/${encodeURIComponent(leagueId)}/gm-plan?lens=${encodeURIComponent(lens)}`,
    ),
};
