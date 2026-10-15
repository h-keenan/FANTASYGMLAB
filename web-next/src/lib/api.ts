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

/** GET .../trade-finder's response — the same TradeIdea card shape as
 * Trade Hub (both serialize through modules.trade_hub_engine's shared card
 * projection), restricted to whatever player_ids the caller selected.
 * Deliberately a narrower type than TradeHubResponse rather than reusing it:
 * this endpoint never returns an `entitlement` key at all (see that
 * endpoint's own docstring — Trade Finder isn't free-tier-limited the way
 * Trade Hub's board is), so typing it as TradeHubResponse the way mobile's
 * api.ts does would claim a field that's never actually on the wire. */
export interface TradeFinderResponse {
  ok: boolean;
  ideas: TradeIdea[];
  reason: string;
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

/** A second named player on a general-News item that resolved to exactly
 * two distinct players (e.g. a two-player trade) — modules.news.
 * _attach_general_news_player_identity's `matched_players` shape. Position/
 * team are omitted from the JSON entirely (not sent as null) whenever that
 * player's row carries no value, so both stay optional here. */
export interface NewsPlayerIdentity {
  matched_player: string | null;
  matched_player_id: string | null;
  matched_player_position?: string | null;
  matched_player_team?: string | null;
}

/** One curated NFL news item — base shape shared by GET /v1/news (the
 * general, non-roster-scoped feed, Revision 10) and GET .../alerts (the
 * roster-scoped feed below, via AlertItem extends NewsItem) rather than two
 * independently drifting copies of the same seven fields. Mirrors mobile's
 * NewsItem (mobile/src/lib/api.ts).
 *
 * matched_player/_id/_position/_team describe the single player an item
 * resolved to; matched_players carries both when it resolved to exactly
 * two instead (see NewsPlayerIdentity) — the general feed can set either,
 * Alerts' roster-scoped feed only ever sets the single-player fields. */
export interface NewsItem {
  title: string | null;
  link: string | null;
  source: string | null;
  summary: string | null;
  published_ts: number | null;
  event_type: string | null;
  speculative: boolean;
  matched_player?: string | null;
  matched_player_id?: string | null;
  matched_player_position?: string | null;
  matched_player_team?: string | null;
  matched_players?: [NewsPlayerIdentity, NewsPlayerIdentity];
}

export interface NewsResponse {
  ok: boolean;
  items: NewsItem[];
}

/** One roster-relevant news item — mirrors mobile's AlertItem (mobile/src/
 * lib/api.ts), the reference implementation for GET .../alerts. That
 * endpoint's own docstring is explicit that this is "one league's feed,
 * not the web app's full Alerts notification system" (Streamlit's
 * modules/alerts_activity.py timeline, which also folds in the Dashboard-
 * style action-item inbox with its own trade_hub/waivers/my_team/rankings
 * destinations) — read state here is real, but there is no destination
 * routing to port: every item's only two CTAs are the source article link
 * and the matched player's identity, same as mobile's screen. */
export interface AlertItem extends NewsItem {
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

/** League-adjusted player rankings (GET .../rankings) — mirrors mobile's
 * RankedPlayer (mobile/src/lib/api.ts) exactly, the reference shape for
 * this endpoint. GM Targets (Revision 11) is this app's first caller; a
 * future Players/Player Detail page should reuse this same type rather
 * than hand-rolling a second one. */
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
  overall_rating?: number | null;
}

export interface LeagueRankingsResponse {
  ok: boolean;
  players: RankedPlayer[];
}

/** A saved GM Targets watchlist row (GET/POST/DELETE/PATCH .../gm-targets) —
 * preference data only (identity + the one user-set `untouchable` flag);
 * name/position/team/rank are joined client-side from LeagueRankingsResponse,
 * the same client-side-join contract mobile's GmTargetsScreen.tsx already
 * uses against this exact pair of endpoints (no duplicate enrichment logic
 * written here — see modules/gm_targets.py for the real source of truth). */
export interface GmTarget {
  player_id: string;
  source_surface: string;
  created_at: string | null;
  untouchable: boolean;
}

export interface GmTargetsResponse {
  ok: boolean;
  targets: GmTarget[];
}

export type GmTargetMutationReason = "" | "at_cap" | "not_available" | "not_found";

export interface GmTargetMutationResponse {
  ok: boolean;
  reason: GmTargetMutationReason;
  cap?: number;
}

/** The weekly-recency usage read (modules.rankings.recency_trend_display,
 * mirrored by mobile's UsageTrend) — only the fields Player Compare
 * (Revision 12) renders; null whenever the sample is too thin to narrate,
 * same gate every other surface already honors. */
export interface UsageTrend {
  direction: "up" | "down";
  trend_pct: number;
  confidence_label: string;
  arrow: string;
  tone: "positive" | "negative";
}

/** GET /v1/players/{id}/quick-view's `model` field — the same composite
 * Market/Opportunity/Scarcity/Role/Age/Confidence breakdown mobile's
 * PlayerDetailScreen ModelSection and app.py's Player Quick View dialog both
 * render for one player, reused (never recomputed) for Player Compare's
 * head-to-head rows. `stats`/`bio` are left untyped: Player Compare only
 * reads `model`, the same scoping mobile's own Compare screen uses (it
 * never fetches season stats/bio for its two sides either). */
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
  decision_fit_narrative: string | null;
}

export interface QuickViewResponse {
  ok: boolean;
  stats: unknown;
  bio: unknown;
  model: QuickViewModel | null;
  reason: "" | "not_found";
}

/**
 * League Recaps / History (Revision 13) — mirrors mobile's RecapStory/
 * WeeklyRecap/RecapResponse types (mobile/src/lib/api.ts) exactly; both
 * clients read the identical GET /v1/leagues/{id}/recap response built by
 * modules.league_recaps.build_weekly_recap. `history_filter` is this web
 * app's own addition on top of the mobile shape (modules/league_recaps.py's
 * story payload already carries it) so the History deep-link affordance
 * (recap_story_html's data-route) has something to route with.
 */
export interface RecapStory {
  story_type: string;
  title: string;
  summary: string;
  glyph: string;
  primary_team: string;
  secondary_team: string;
  primary_roster_id: string;
  secondary_roster_id: string;
  players: string[];
  metric_label: string;
  metric_value: string;
  history_week: number;
  confidence: string;
  editorial_label?: string;
  history_filter?: string;
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
  ok: boolean;
  recap: WeeklyRecap | null;
  reason: "" | "no_completed_week";
  max_completed_week: number;
}

/** One side of a History transaction — modules.league_history.normalize_transaction's
 * `sides[]` shape, verbatim. */
export interface HistoryAsset {
  kind: "player" | "pick";
  player_id: string;
  name: string;
  position: string;
  team: string;
  label: string;
  known: boolean;
  season?: string;
  round?: number | null;
}

export interface HistorySide {
  roster_id: string;
  team_name: string;
  owner_handle: string;
  avatar_url: string;
  receives: HistoryAsset[];
  drops: HistoryAsset[];
  faab_spent: number | null;
  faab_received: number | null;
}

/** Retrospective grade — modules.transaction_grades.grade_transaction's
 * output, verbatim (grade_trade for `kind === "trade"`, grade_waiver
 * otherwise). No scoring math on this side; this type only names the
 * fields transaction_grades_ui.py's HTML renderers already read. */
export interface HistoryGradeSide {
  team: string;
  letter: string;
  tone: string;
  confidence: string;
  why: string;
  watch?: string;
}

export interface HistoryGrade {
  kind: string;
  pending: boolean;
  partial_evidence?: boolean;
  provisional?: boolean;
  sides?: HistoryGradeSide[];
  // Waiver/free-agent shape — flat, not a `sides[]` list.
  player?: string;
  team?: string;
  letter?: string;
  tone?: string;
  confidence?: string;
  why?: string;
  watch?: string;
  grade_model_label?: string;
}

export interface HistoryTransaction {
  transaction_id: string;
  season: string;
  league_id: string;
  week: number;
  timestamp: number;
  type: "trade" | "waiver" | "free_agent";
  draft_picks: HistoryAsset[];
  sides: HistorySide[];
  grade: HistoryGrade | null;
}

export interface HistorySeason {
  league_id: string;
  season: string;
  name: string;
}

export type HistoryReason = "" | "no_history";

export interface HistoryResponse {
  ok: boolean;
  seasons: HistorySeason[];
  selected_league_id: string;
  transactions: HistoryTransaction[];
  reason: HistoryReason;
}

// Draft Center (Revision 14) — GET .../draft-center's Overview pane only
// (your own draft posture + league-wide decision/partner cards); see that
// endpoint's own docstring for why Current Draft/History (live draft board)
// and Scouting are real, separate surfaces not covered here or by mobile's
// DraftCenterScreen.tsx, which this page mirrors exactly.
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

// Every draft pick asset in the league, with its full PQV-style valuation
// breakdown — shared verbatim with mobile's Pick Detail screen and the
// mobile Trade Analyzer's Players/Picks roster browser (see GET
// .../draft-picks's own docstring). This page only reads the identity/
// value fields (score, round, tier, projected range, confidence); the rest
// of the breakdown is forwarded but unused here, same restraint mobile's
// DraftCenterScreen.tsx (as opposed to its PickDetailScreen) takes.
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
  tier_bucket?: string | null;
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

export interface DraftPicksResponse {
  ok: true;
  picks: DraftPickAsset[];
  reason: string;
}

// Trade Analyzer (Revision 15) — raw Sleeper passthrough rosters/users and
// the derived team-profile map, mirroring mobile/src/lib/api.ts's
// LeagueUsersResponse/LeagueRostersResponse/TeamProfile exactly. These three
// already back mobile's own Trade Analyzer roster-browse (who's on which
// team, whose roster to search for the receive side) — no new backend logic,
// only wiring the same GET /users, /rosters, /team-profiles this web app's
// Next.js client had never called before.
export interface LeagueUsersResponse {
  ok: boolean;
  users: Array<Record<string, unknown>>;
}

export interface LeagueRostersResponse {
  ok: boolean;
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
  ok: boolean;
  profiles: Record<string, TeamProfile>;
}

/** The one specific asset a verdict's counter_guidance identified (never a
 * generic suggestion) — modules.trade_offer_analyzer.build_counter_guidance's
 * `action` dict, verbatim. Lets "Build the counter" apply it directly to the
 * package instead of the user re-reading the sentence and hunting for the
 * player themselves. */
export interface TradeCounterAction {
  action: "remove_from_send" | "add_to_receive";
  player_id: string;
  asset_type: string;
  label: string;
}

/** A real alternate package ("Try this instead") the server actually
 * regraded as Fair/Accept — modules.trade_offer_analyzer.build_counter_offer_packages's
 * `_package_entry`, verbatim. Empty on the verdict whenever no clean
 * rebalancing was found; never fabricated client-side. */
export interface TradeAlternatePackage {
  label: string;
  send_assets: TradeAsset[];
  receive_assets: TradeAsset[];
  band: string;
  ui_verdict: string;
  confidence: string;
  value_delta: number;
}

/** modules/trade_offer_analyzer.py's OfferVerdict.to_public_dict(), verbatim
 * — the real accept/decline/counter verdict for a manually-built trade
 * package. Mirrors mobile's TradeVerdict (mobile/src/lib/api.ts) plus
 * `alternate_packages`, which mobile's screen doesn't render but the
 * Streamlit card does (see build_offer_result_card_html's "Try this
 * instead" section) — included here for parity with the page this ports. */
export interface TradeVerdict {
  band: string;
  ui_verdict: "ACCEPT" | "DECLINE" | "COUNTER" | "FAIR";
  confidence: string;
  rationale: string;
  value_summary: string;
  roster_summary: string;
  strategy_summary: string;
  risk_summary: string;
  counter_guidance: string;
  fit_total: number;
  value_delta: number;
  tone: "accept" | "counter" | "decline" | "fair";
  counter_action?: TradeCounterAction | null;
  alternate_packages?: TradeAlternatePackage[];
}

export type TradeAnalyzerReason =
  | ""
  | "no_sleeper_username_linked"
  | "sleeper_user_not_found"
  | "not_a_member_of_league"
  | "no_player_data"
  | "empty_roster"
  | "assets_not_found"
  | "fit_unavailable";

export interface TradeAnalyzerResponse {
  ok: boolean;
  verdict: TradeVerdict | null;
  reason: TradeAnalyzerReason;
}

/** Trade History (Revision 18) — modules/trade_outcome_results.py's quiet
 * "did it work out?" follow-up, mirrored verbatim from mobile/src/lib/api.ts
 * (TradeOutcomeAssetSummary/TradeOutcomeSummary/TradeOutcomeResultSummary/
 * PastTradeOutcome/TradeOutcomeHistoryResponse). Distinct taxonomy from
 * League Recaps/History's letter grades (modules.transaction_grades) — this
 * only covers trades the user confirmed actually happened, graded by real
 * before/after production + value trend, never a provisional in-flight
 * letter grade. */
export interface TradeOutcomeAssetSummary {
  name: string;
  position: string;
  player_id?: string;
  value_score?: number | null;
}

export interface TradeOutcomeSummary {
  partner_team_name: string;
  send: TradeOutcomeAssetSummary[];
  receive: TradeOutcomeAssetSummary[];
  value_edge_label: string;
  valuation_lens?: string;
}

export interface TradeOutcomeResultSummary {
  status: "ready" | "insufficient_data";
  reason: string;
  verdict: "worked_out" | "didnt_pan_out" | "mixed" | "neutral" | null;
  verdict_label?: string;
  confidence?: "low" | "medium" | "high";
  days_since_trade: number | null;
  production?: { net_points_ppr: number; avg_net_per_week: number; weeks_counted: number } | null;
  value?: { sent_delta_pct: number; received_delta_pct: number; net_delta_pct: number } | null;
}

export interface PastTradeOutcome {
  id: string;
  league_id: string;
  partner_team_name: string;
  trade_summary: TradeOutcomeSummary;
  outcome: "yes" | "no" | "didnt_send";
  shared_at: string;
  outcome_recorded_at: string | null;
  result_summary: TradeOutcomeResultSummary | null;
  result_computed_at: string | null;
}

export interface TradeOutcomeHistoryResponse {
  ok: boolean;
  outcomes: PastTradeOutcome[];
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

  // "Select these specific players, find who'd want them" — same engine/
  // Trust enforcement/card shape as getTradeHub, restricted to playerIds.
  // An empty playerIds list is a legitimate call (the endpoint itself
  // returns `reason: "no_players_selected"` rather than erroring), but the
  // UI never actually calls this with an empty selection — see
  // TradeFinderContent's disabled-button gate.
  getTradeFinderIdeas: (
    leagueId: string,
    playerIds: string[],
    strategy: string = "retool",
    lens: string = "Dynasty",
  ) =>
    authorizedRequest<TradeFinderResponse>(
      `/v1/leagues/${encodeURIComponent(leagueId)}/trade-finder?player_ids=${encodeURIComponent(playerIds.join(","))}&strategy=${encodeURIComponent(strategy)}&lens=${encodeURIComponent(lens)}`,
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

  // General, non-roster-scoped NFL news (Revision 10) — same GET /v1/news
  // mobile's NewsScreen reads, and league-independent like getPortfolio
  // above: no leagueId param.
  getNews: (limit: number = 30) =>
    authorizedRequest<NewsResponse>(`/v1/news?limit=${limit}`),

  // League-adjusted player rankings — GM Targets (Revision 11) joins this
  // against getGmTargets' bare preference rows for name/position/team/rank/
  // injury, the same client-side join mobile's GmTargetsScreen.tsx does.
  getLeagueRankings: (leagueId: string, lens: string = "Dynasty", limit: number = 300) =>
    authorizedRequest<LeagueRankingsResponse>(
      `/v1/leagues/${encodeURIComponent(leagueId)}/rankings?lens=${encodeURIComponent(lens)}&limit=${limit}`,
    ),

  // GM Targets (Revision 11) — the GM_TOOLS watchlist. Reads/writes the
  // exact same durable table (modules/gm_targets.py) and endpoints mobile's
  // GmTargetsScreen.tsx already calls; no new backend logic for this page.
  getGmTargets: (leagueId: string) =>
    authorizedRequest<GmTargetsResponse>(`/v1/leagues/${encodeURIComponent(leagueId)}/gm-targets`),
  removeGmTarget: (leagueId: string, playerId: string) =>
    authorizedRequest<GmTargetMutationResponse>(
      `/v1/leagues/${encodeURIComponent(leagueId)}/gm-targets/${encodeURIComponent(playerId)}`,
      { method: "DELETE" },
    ),
  setGmTargetUntouchable: (leagueId: string, playerId: string, untouchable: boolean) =>
    authorizedRequest<GmTargetMutationResponse>(
      `/v1/leagues/${encodeURIComponent(leagueId)}/gm-targets/${encodeURIComponent(playerId)}/untouchable`,
      { method: "PATCH", jsonBody: { untouchable } },
    ),

  // Player Compare (Revision 12) — league-independent, same endpoint mobile's
  // PlayerCompareScreen calls twice (once per side) via getPlayerQuickView.
  getPlayerQuickView: (playerId: string) =>
    authorizedRequest<QuickViewResponse>(`/v1/players/${encodeURIComponent(playerId)}/quick-view`),

  // League Recaps / History (Revision 13) — Recaps tab shares mobile's
  // RecapScreen endpoint exactly (see RecapResponse's docstring); History
  // is a new thin wrapper (GET .../history) over the same
  // modules.league_history / modules.transaction_grades the web app's
  // Streamlit History tab already used.
  getLeagueRecap: (leagueId: string, week?: number) =>
    authorizedRequest<RecapResponse>(
      `/v1/leagues/${encodeURIComponent(leagueId)}/recap${week ? `?week=${week}` : ""}`,
    ),

  getLeagueHistory: (leagueId: string, seasonLeagueId?: string) =>
    authorizedRequest<HistoryResponse>(
      `/v1/leagues/${encodeURIComponent(leagueId)}/history${
        seasonLeagueId ? `?season_league_id=${encodeURIComponent(seasonLeagueId)}` : ""
      }`,
    ),

  // Draft Center (Revision 14) — same two endpoints mobile's
  // DraftCenterScreen.tsx calls (Overview pane + pick assets); no new
  // backend logic for this page.
  getLeagueDraftCenter: (leagueId: string, lens: string = "Dynasty") =>
    authorizedRequest<DraftCenterResponse>(
      `/v1/leagues/${encodeURIComponent(leagueId)}/draft-center?lens=${encodeURIComponent(lens)}`,
    ),

  getLeagueDraftPicks: (leagueId: string, lens: string = "Dynasty") =>
    authorizedRequest<DraftPicksResponse>(
      `/v1/leagues/${encodeURIComponent(leagueId)}/draft-picks?lens=${encodeURIComponent(lens)}`,
    ),

  // Trade Analyzer (Revision 15) — roster-browse identity data, same three
  // endpoints mobile's TradeAnalyzerScreen.tsx calls alongside getMyRoster/
  // getLeagueRankings/getLeagueDraftPicks to build its "which team am I
  // browsing" picker.
  getLeagueUsers: (leagueId: string) =>
    authorizedRequest<LeagueUsersResponse>(`/v1/leagues/${encodeURIComponent(leagueId)}/users`),
  getLeagueRosters: (leagueId: string) =>
    authorizedRequest<LeagueRostersResponse>(`/v1/leagues/${encodeURIComponent(leagueId)}/rosters`),
  getLeagueTeamProfiles: (leagueId: string) =>
    authorizedRequest<LeagueTeamProfilesResponse>(
      `/v1/leagues/${encodeURIComponent(leagueId)}/team-profiles`,
    ),

  // The real accept/decline/counter verdict for a manually-built trade
  // package — same POST .../trade-analyzer mobile's "Analyze Trade" button
  // calls (modules.trade_analyzer_fit + modules.trade_offer_analyzer; no
  // valuation logic duplicated here).
  postTradeAnalyzer: (
    leagueId: string,
    body: {
      sendPlayerIds: string[];
      receivePlayerIds: string[];
      sendPickIds?: string[];
      receivePickIds?: string[];
      strategy?: string;
      lens?: string;
      partnerRosterId?: string;
    },
  ) =>
    authorizedRequest<TradeAnalyzerResponse>(
      `/v1/leagues/${encodeURIComponent(leagueId)}/trade-analyzer`,
      {
        method: "POST",
        jsonBody: {
          send_player_ids: body.sendPlayerIds,
          receive_player_ids: body.receivePlayerIds,
          send_pick_ids: body.sendPickIds ?? [],
          receive_pick_ids: body.receivePickIds ?? [],
          strategy: body.strategy ?? "retool",
          lens: body.lens ?? "Dynasty",
          partner_roster_id: body.partnerRosterId ?? "",
        },
      },
    ),

  // Trade History (Revision 18) — every confirmed ('yes'/'no'/'didnt_send')
  // trade_outcomes row for the signed-in user across ALL their leagues, same
  // GET /v1/trade-outcomes/history mobile's TradeHistoryScreen.tsx calls.
  // League-independent like getPortfolio/getNews above: no leagueId param.
  getTradeOutcomeHistory: () =>
    authorizedRequest<TradeOutcomeHistoryResponse>("/v1/trade-outcomes/history"),
};
