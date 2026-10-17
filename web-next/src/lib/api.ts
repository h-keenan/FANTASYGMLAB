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

export interface BillingPlan {
  tier: "pro" | "front_office";
  interval: "monthly" | "annual";
  label: string;
  price: string;
  cadence: string;
  features: string[];
}

export interface BillingPlansResponse {
  ok: boolean;
  plans: BillingPlan[];
}

export interface BillingCheckoutResponse {
  ok: boolean;
  checkout_url: string;
}

export interface BillingPortalResponse {
  ok: boolean;
  portal_url: string;
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

export interface BriefingMentionedPlayer {
  player_id: string;
  name: string;
  position: string;
  team: string;
  player_tier: string;
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
  // Every player the card's text actually names (e.g. Injury Alert's "3
  // injured starters") — not just the single route_player_* above. Empty
  // for every single-player tile.
  mentioned_players: BriefingMentionedPlayer[];
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
  /** Trade Finder is Premium-only (matches app.py's current_user_is_premium()
   * gate) — a Free caller gets an empty idea list plus `upsell` instead of
   * real search results. */
  is_premium: boolean;
  upsell: PremiumUpsell | null;
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
  /** This week's per-game projection, reusing the exact same projection
   * real_starters already carry — null only when the backend had no
   * live lineup context to enrich from (see services.mobile_api_service's
   * _matchup_side docstring). coridian_, 2026-10-17: "everyy player on the
   * matchup screen needs a projection." */
  projection: PlayerWeekProjection | null;
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

/** modules.matchup_win_probability.compute_live_win_probability's output —
 * a real Normal-difference model over each side's real_starters (actual
 * points once a game's started, this week's projection otherwise), never
 * a guessed 50/50. `available` is false (not a fabricated number) when
 * either side's modeled coverage is below the documented floor — see that
 * module's own docstring for why. */
export interface MatchupWinProbability {
  available: boolean;
  reason?: "no_starters" | "insufficient_coverage";
  /** 0-1, this user's own side's win chance. */
  probability?: number;
  my_projected_total?: number;
  opponent_projected_total?: number;
  coverage?: { my: number; opponent: number };
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
  win_probability: MatchupWinProbability | null;
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

/** Shared shape for every Premium-only endpoint's Free-tier response —
 * Portfolio, GM Plan, and Trade Finder all return this same {title, body}
 * instead of each inventing its own upsell type. */
export interface PremiumUpsell {
  title: string;
  body: string;
}

/** @deprecated use PremiumUpsell — kept so existing imports don't break. */
export type PortfolioUpsell = PremiumUpsell;

export interface PortfolioResponse {
  ok: boolean;
  is_premium: boolean;
  lens: string;
  leagues: PortfolioLeague[];
  failed_leagues: PortfolioFailedLeague[];
  /** Present only for a Free caller — Portfolio needs more than the one
   * league Free accounts can save, so Free gets this honest upsell instead
   * of an empty or broken screen. */
  upsell: PremiumUpsell | null;
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
  /** GM Plan is Premium-only (matches app.py's render_gm_plan... gate) — a
   * Free caller gets `quiet: true` plus `upsell` instead of a real roadmap. */
  is_premium: boolean;
  upsell: PremiumUpsell | null;
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

/** Team Situation (Revision 19) — a durable, user-declared GM stance:
 * Rebuilding/Competing/Balanced (modules/team_stance.py, GET/POST
 * .../team-stance). Mirrors mobile's TeamStance/TEAM_STANCE_OPTIONS
 * (mobile/src/lib/api.ts) exactly, including the option copy. Unlike
 * Streamlit's own route (app.py's "team_stance" page, which can't feed this
 * value into its separate, pre-existing valuation override), this FastAPI
 * endpoint's `strategy` field IS the same real input that already drives
 * Trade Hub/GM Plan/Dashboard's age-curve and pick-value math on this data
 * path (see _fetch_gm_stance_with_set_flag's callers in
 * services/mobile_api_service.py) — so declaring a stance here has the same
 * real effect it does on mobile. */
export type TeamStance = "rebuilding" | "competing" | "balanced";

export const TEAM_STANCE_OPTIONS: Array<{ value: TeamStance; label: string; description: string }> = [
  { value: "rebuilding", label: "Rebuilding", description: "Prioritize youth and future draft capital" },
  { value: "competing", label: "Competing", description: "Prioritize immediate roster impact" },
  { value: "balanced", label: "Balanced", description: "Keep both current value and future flexibility" },
];

export interface TeamStanceResponse {
  ok: boolean;
  stance: TeamStance | "";
  options?: TeamStance[];
  strategy?: string;
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

/** GET /v1/players/{id}/weekly-stats — per-week PPR points + snap share for
 * one player/season, mirrors mobile/src/lib/api.ts's identically-named
 * types byte-for-byte (same `services/mobile_api_service.py` response both
 * clients read). Powers Player Compare's "Points By Week" dual chart
 * (Revision 14): no new backend surface, this endpoint already existed for
 * mobile's Player Detail chart and app.py's own Points By Week section. */
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

/** GET /v1/players/{id}/quick-view's `model` field — the same composite
 * Market/Opportunity/Scarcity/Role/Age/Confidence breakdown mobile's
 * PlayerDetailScreen ModelSection and app.py's Player Quick View dialog both
 * render for one player, reused (never recomputed) for Player Compare's
 * head-to-head rows and for the shared PlayerQuickView modal (Revision 22).
 * `market_rating`/`opportunity_rating`/`scarcity_rating`/`role_rating`/
 * `durability_rating` are the same four composite inputs (plus a durability
 * read) re-expressed on the 0-99 OVR-ring scale — see
 * modules.player_quick_view.sub_ratings — spread into this same dict by
 * _project_player_model server-side; absent fields are always present as
 * keys (nullable), never missing. */
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
  market_rating?: number | null;
  opportunity_rating?: number | null;
  scarcity_rating?: number | null;
  role_rating?: number | null;
  durability_rating?: number | null;
}

/** One stat row inside QuickViewSeason/QuickViewStats — mirrors
 * modules.player_quick_view.StatItem / mobile's QuickViewStatItem exactly.
 * `percentile` (1-100, within the player's position pool) is null whenever
 * the comparison pool was too thin to rank against
 * (modules.player_quick_view.PERCENTILE_MIN_POOL) — never a fabricated
 * number. */
export interface QuickViewStatItem {
  label: string;
  value: string;
  note: string;
  tone: string;
  percentile: number | null;
}

/** One season's stat breakdown — mirrors
 * modules.player_quick_view.SeasonStatView / mobile's QuickViewSeason. */
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

/** GET /v1/players/{id}/quick-view's `stats` field — mirrors
 * modules.player_quick_view.PlayerQuickViewStats / mobile's QuickViewStats.
 * `overall_rating` (0-99, the player's value_score percentile at their
 * position re-expressed on the 2K "OVR" scale) and `prime_window` are both
 * null under the same thin-pool gate as every StatItem.percentile above. */
export interface QuickViewStats {
  seasons: QuickViewSeason[];
  college: QuickViewStatItem[];
  college_available: boolean;
  career_totals_available: boolean;
  position: string;
  overall_rating: number | null;
  prime_window: Record<string, unknown> | null;
}

/** GET /v1/players/{id}/quick-view's `bio` field — mirrors
 * modules.player_quick_view.ExecutiveSnapshot / mobile's QuickViewBio.
 * Every field is already-normalized display text (or "" when unavailable),
 * never a raw unformatted column value. */
export interface QuickViewBio {
  years_in_league: string;
  draft_capital: string;
  college: string;
  height: string;
  weight: string;
  bye_week: string;
  contract_status: string;
}

export interface QuickViewResponse {
  ok: boolean;
  stats: QuickViewStats | null;
  bio: QuickViewBio | null;
  model: QuickViewModel | null;
  reason: "" | "not_found";
}

/** GET /v1/players/{id}/awards' response — mirrors
 * modules.player_awards.PlayerBadge / mobile's PlayerAward. Deterministic,
 * verified fantasy-performance badges only — never invented, never
 * AI-generated, never presented as an official NFL honor. Empty `awards`
 * means no qualifying season on file, not an error. */
export interface PlayerAward {
  badge_id: string;
  category: string;
  family: string;
  title: string;
  short_label: string;
  tier: "gold" | "silver" | "bronze" | null;
  season: number | null;
  rank: number | null;
  metric_value: number | null;
  description: string;
  occurrence_count: number;
}

export interface PlayerAwardsResponse {
  ok: boolean;
  awards: PlayerAward[];
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

/**
 * League Recaps / History — Storylines tab (Revision 15). Mirrors
 * modules.league_storylines.build_league_storylines's output verbatim; the
 * new GET .../storylines endpoint is a thin wrapper that calls it with the
 * current season's normalized History transactions, the same input shape
 * the Streamlit Storylines tab (modules/league_storylines_ui.py) builds
 * from modules.league_history_ui.cached_season_history_payload. No award
 * selection/ranking math lives in this client — only display formatting.
 */
export interface StorylineTeam {
  roster_id: string;
  team_name: string;
  owner_handle: string;
  avatar_url: string;
}

export interface StorylineLeader extends StorylineTeam {
  metric: number;
  tied: boolean;
  breakdown?: { trade: number; waiver: number; free_agent: number };
}

export interface StorylineLargestTrade {
  transaction_id: string;
  week: number;
  timestamp: number;
  when: string;
  teams: StorylineTeam[];
  players: number;
  picks: number;
  assets: number;
}

export interface StorylineBiggestFaab extends StorylineTeam {
  amount: number;
  transaction_id: string;
  week: number;
  timestamp: number;
  when: string;
  player: HistoryAsset | Record<string, never>;
}

export interface StorylineBusiestWeek {
  week: number;
  count: number;
}

export interface StorylineMostTradedPlayer {
  count: number;
  player: HistoryAsset;
}

export interface LeagueStorylinesReport {
  season: string;
  transaction_count: number;
  most_active: StorylineLeader | null;
  trade_market_leader: StorylineLeader | null;
  most_picks_acquired: StorylineLeader | null;
  roster_turnover: StorylineLeader | null;
  largest_trade: StorylineLargestTrade | null;
  biggest_faab: StorylineBiggestFaab | null;
  quietest: StorylineLeader | null;
  busiest_week: StorylineBusiestWeek | null;
  most_traded_player: StorylineMostTradedPlayer | null;
}

export interface StorylinesResponse {
  ok: boolean;
  storylines: LeagueStorylinesReport | null;
  reason: string;
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

// College Scouting (Revision 20) — the shared, crowdsourced college prospect
// catalog (modules/college_scouting.py / GET /v1/scouting/prospects). Every
// signed-in user grades the same prospect pool; the pooled aggregate (never
// any single grade) is what can influence draft-class strength. Types mirror
// mobile/src/lib/api.ts's CollegeProspect/CollegeProspectsResponse exactly —
// same shared backend, same shape, no new fields invented here.
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
  ok: boolean;
  prospects: CollegeProspect[];
  // False when the real Supabase catalog isn't configured/migrated/
  // reachable yet. There is no fabricated-data fallback — `prospects` is
  // simply empty in that case (modules.college_scouting's "NO FABRICATED
  // DATA" policy), and the page's own empty state covers it.
  catalog_available: boolean;
  reason: string;
}

export interface ScoutingMutationResponse {
  ok: boolean;
  reason: string;
}

// Mirrors modules/college_scouting.py's MIN_GRADE/MAX_GRADE/
// MIN_ROUND_PROJECTION/MAX_ROUND_PROJECTION exactly (same constants
// mobile/src/lib/api.ts exports) — the server is the real source of truth
// (422s outside this range), these just keep the grading UI's picker
// options in sync without a round trip.
export const MIN_GRADE = 1;
export const MAX_GRADE = 5;
export const MIN_ROUND_PROJECTION = 1;
export const MAX_ROUND_PROJECTION = 7;

// Live Draft (Revision 21) — the last page on the original migration punch
// list. Unlike every earlier revision, there is no mobile reference
// screen to port: Live Draft only ever existed in Streamlit
// (modules/live_draft_ui.py's render_live_draft_page), a read-only Sleeper
// draft-room mirror that polls every LIVE_DRAFT_POLL_INTERVAL_SECONDS
// (12s). GET .../live-draft and GET .../live-draft/{draft_id} are brand
// new backend endpoints (services/mobile_api_service.py) wrapping
// modules/live_draft.py's discover_live_drafts/build_live_draft_state
// verbatim — no new scoring/ranking logic duplicated in this client.
export interface LiveDraftSummary {
  draft_id: string;
  season: string;
  status: "drafting" | "paused" | "pre_draft" | "complete" | string;
  rounds: number;
  name: string;
}

export interface LiveDraftDiscoveryResponse {
  ok: boolean;
  error: string;
  drafts: LiveDraftSummary[];
  active_draft_id: string;
}

export interface LiveDraftPickRow {
  pick_no: number;
  round: number;
  round_pick: string;
  player_id: string;
  player_name: string;
  position: string;
  team: string;
  fantasy_team: string;
  is_mine: boolean;
}

export interface LiveDraftRecommendation {
  player_id: string;
  name: string;
  position: string;
  team: string;
  age: number | null;
  tier: string;
  league_adjusted_draft_score: number | null;
  overall_rating: number | null;
  recommendation_role: string;
  recommendation_reason: string;
  position_need_impact: string;
  immediate_roster_impact: string;
  confidence: string;
  adp_delta: number | null;
}

export interface LiveDraftRankingRow {
  player_id: string;
  name: string;
  position: string;
  team: string;
  age: number | null;
  tier: string;
  is_rookie: boolean;
  overall_rank: number | null;
  position_rank: number | null;
  canonical_overall_rank: number | null;
  canonical_position_rank: number | null;
  rank_scoring_format: string;
  rank_unavailable_reason: string;
  base_value: number | null;
  league_adjusted_draft_score: number | null;
  overall_rating: number | null;
  // Always 0 straight off this endpoint — there's no server session to
  // diff against a previous poll. The client computes the real delta
  // itself from two consecutive polls (see lib/liveDraftPresentation.ts).
  movement: number;
  recommendation_label: string;
  recommendation_reason: string;
}

export interface LiveDraftTeamRow {
  roster_id: number;
  team_name: string;
  is_mine: boolean;
  team_rank: number;
  movement: number;
  trend_label: string;
  live_team_score: number;
  roster_count: number;
  pick_count: number;
  positions: string;
  top_player: string;
  starter_value: number;
  total_value: number;
}

export interface LiveDraftStateResponse {
  ok: boolean;
  reason: string;
  pick_data_stale: boolean;
  status: "drafting" | "paused" | "pre_draft" | "complete" | string;
  rounds: number;
  teams: number;
  picks_made: number;
  current_pick: number;
  current_round: number;
  current_team_name: string;
  current_manager_name: string;
  my_slot: number;
  is_my_pick: boolean;
  picks_until_mine: number | null;
  my_upcoming_picks: number[];
  positional_run: string;
  last_updated: string;
  score_label: string;
  league_settings: {
    qb_format: string;
    scoring_format: string;
    league_format: string;
  };
  recommendations: LiveDraftRecommendation[];
  pick_rows: LiveDraftPickRow[];
  rankings: LiveDraftRankingRow[];
  team_rankings: LiveDraftTeamRow[];
}

/** The hypothetical mid-draft Trade Evaluator's own pair of endpoints —
 * split from LiveDraftStateResponse above because it needs a different
 * shape (a labeled not-yet-made pick slot to select, then a submitted
 * send/receive package to score), not another poll. Mirrors
 * modules/live_draft_trade_evaluator.py verbatim; see GET/POST
 * .../trade-evaluator's own docstrings in services/mobile_api_service.py
 * for the full reuse chain. */
export interface LiveDraftPickOption {
  pick_key: string;
  label: string;
}

export interface LiveDraftTradeEvaluatorOptionsResponse {
  ok: boolean;
  reason: string;
  pick_data_stale: boolean;
  pick_options: LiveDraftPickOption[];
}

/** One send/receive asset, already shaped like the app's existing
 * `TradeAsset` (lib/api.ts) so TradeAssetRow/ExchangeSide render it with no
 * second adapter — season/round come back as strings here (unlike the
 * evaluator module's own int fields) to match that shape exactly. */
export interface LiveDraftTradeAsset {
  asset_type: "player" | "pick";
  player_id: string | null;
  name: string | null;
  label: string | null;
  position: string | null;
  team: string | null;
  age: number | null;
  score: number | null;
  injury_status: string | null;
  tier: string | null;
  season: string | null;
  round: string | null;
  owner_team_name: string | null;
}

export interface LiveDraftTradeEvaluatorResponse {
  ok: boolean;
  reason: "" | "stale_picks" | "assets_not_found" | "no_player_data";
  stale_pick_keys: string[];
  send_assets?: LiveDraftTradeAsset[];
  receive_assets?: LiveDraftTradeAsset[];
  send_total?: number;
  receive_total?: number;
  delta?: number;
  verdict?: string;
}

export const api = {
  getMe: () => authorizedRequest<MeResponse>("/v1/me"),

  getBillingPlans: () => authorizedRequest<BillingPlansResponse>("/v1/billing/plans"),

  startBillingCheckout: (
    tier: BillingPlan["tier"],
    interval: BillingPlan["interval"],
    returnTo?: string,
  ) =>
    authorizedRequest<BillingCheckoutResponse>("/v1/billing/checkout", {
      method: "POST",
      jsonBody: { tier, interval, ...(returnTo ? { return_to: returnTo } : {}) },
    }),

  openBillingPortal: () =>
    authorizedRequest<BillingPortalResponse>("/v1/billing/portal", { method: "POST" }),

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

  // Raw Sleeper league payload — used only for league.settings.type (0 =
  // redraft, 1 = keeper, 2 = dynasty), to seed ValuationLensContext's
  // per-league default with the league's real structural format instead of
  // always assuming Dynasty (coridian_, 2026-10-17: "it should always
  // check to see if the league is a dynasty or not... if it's redraft, it
  // should not automatically input that as dynasty"). Mirrors
  // modules.league_value_settings.detect_league_value_settings_from_payload's
  // exact same mapping.
  getLeague: (leagueId: string) =>
    authorizedRequest<{ ok: boolean; league: { settings?: { type?: number } } }>(
      `/v1/leagues/${encodeURIComponent(leagueId)}`,
    ),

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
  // Team Situation (Revision 19) is the one other caller of this add path —
  // protecting a player not yet watched adds it first (source_surface
  // "team_stance"), same as mobile's TeamStanceScreen.tsx. GM Targets' own
  // page still has no in-page add flow (see GmTargetsContent's docstring).
  addGmTarget: (leagueId: string, playerId: string, sourceSurface = "gm_targets") =>
    authorizedRequest<GmTargetMutationResponse>(`/v1/leagues/${encodeURIComponent(leagueId)}/gm-targets`, {
      method: "POST",
      jsonBody: { player_id: playerId, source_surface: sourceSurface },
    }),
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
  // Team Situation (Revision 19) — GET/POST .../team-stance, the same
  // endpoints mobile's GmStanceContext/TeamStanceScreen already call.
  getTeamStance: (leagueId: string) =>
    authorizedRequest<TeamStanceResponse>(`/v1/leagues/${encodeURIComponent(leagueId)}/team-stance`),
  setTeamStance: (leagueId: string, stance: TeamStance) =>
    authorizedRequest<TeamStanceResponse>(`/v1/leagues/${encodeURIComponent(leagueId)}/team-stance`, {
      method: "POST",
      jsonBody: { stance },
    }),

  // Player Compare (Revision 12) — league-independent, same endpoint mobile's
  // PlayerCompareScreen calls twice (once per side) via getPlayerQuickView.
  getPlayerQuickView: (playerId: string) =>
    authorizedRequest<QuickViewResponse>(`/v1/players/${encodeURIComponent(playerId)}/quick-view`),

  // Shared PlayerQuickView modal (Revision 22) — the same verified-badges
  // endpoint mobile's PlayerDetailScreen already calls
  // (getPlayerAwards -> GET .../awards). League-independent, same pattern
  // as getPlayerQuickView above.
  getPlayerAwards: (playerId: string) =>
    authorizedRequest<PlayerAwardsResponse>(`/v1/players/${encodeURIComponent(playerId)}/awards`),

  // Player Compare's "Points By Week" dual chart (Revision 14) — same
  // endpoint mobile's Player Detail chart calls (mobile/src/lib/api.ts's
  // getPlayerWeeklyStats), fetched twice (once per side) the same way
  // getPlayerQuickView above already is. Omitting `season` lets the backend
  // default to the current season (sleeper.default_player_stats_season()),
  // the only season Player Compare's dual chart renders for now.
  getPlayerWeeklyStats: (playerId: string, season?: number) =>
    authorizedRequest<WeeklyStatsResponse>(
      `/v1/players/${encodeURIComponent(playerId)}/weekly-stats${season ? `?season=${season}` : ""}`,
    ),

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

  // Storylines tab (Revision 15) — GET .../storylines, the new thin wrapper
  // over modules.league_storylines.build_league_storylines.
  getLeagueStorylines: (leagueId: string) =>
    authorizedRequest<StorylinesResponse>(`/v1/leagues/${encodeURIComponent(leagueId)}/storylines`),

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

  // College Scouting (Revision 20) — league-independent like getPortfolio/
  // getNews/getTradeOutcomeHistory above: the shared prospect pool is the
  // same regardless of which league is selected. Same five /v1/scouting/*
  // endpoints mobile's CollegeProspectsScreen.tsx / ProspectScoutingDetail
  // Screen.tsx already call; no new backend logic for this page.
  getCollegeProspects: () => authorizedRequest<CollegeProspectsResponse>("/v1/scouting/prospects"),
  submitScoutingReport: (
    prospectId: string,
    body: { grade: number; round_projection: number | null; note: string },
  ) =>
    authorizedRequest<ScoutingMutationResponse>(
      `/v1/scouting/prospects/${encodeURIComponent(prospectId)}/report`,
      { method: "POST", jsonBody: body },
    ),
  deleteScoutingReport: (prospectId: string) =>
    authorizedRequest<ScoutingMutationResponse>(
      `/v1/scouting/prospects/${encodeURIComponent(prospectId)}/report`,
      { method: "DELETE" },
    ),
  addProspectToWatchlist: (prospectId: string) =>
    authorizedRequest<ScoutingMutationResponse>(
      `/v1/scouting/watchlist/${encodeURIComponent(prospectId)}`,
      { method: "POST" },
    ),
  removeProspectFromWatchlist: (prospectId: string) =>
    authorizedRequest<ScoutingMutationResponse>(
      `/v1/scouting/watchlist/${encodeURIComponent(prospectId)}`,
      { method: "DELETE" },
    ),

  // Live Draft (Revision 21) — see LiveDraftStateResponse's own comment.
  getLiveDraftDiscovery: (leagueId: string) =>
    authorizedRequest<LiveDraftDiscoveryResponse>(`/v1/leagues/${encodeURIComponent(leagueId)}/live-draft`),
  getLiveDraftState: (leagueId: string, draftId: string, lens: string = "Dynasty") =>
    authorizedRequest<LiveDraftStateResponse>(
      `/v1/leagues/${encodeURIComponent(leagueId)}/live-draft/${encodeURIComponent(draftId)}?lens=${encodeURIComponent(lens)}`,
    ),

  // Hypothetical mid-draft Trade Evaluator — the remaining-pick options to
  // populate the picker (already-drafted players come from
  // LiveDraftStateResponse.pick_rows, already on hand).
  getLiveDraftTradeEvaluatorOptions: (leagueId: string, draftId: string) =>
    authorizedRequest<LiveDraftTradeEvaluatorOptionsResponse>(
      `/v1/leagues/${encodeURIComponent(leagueId)}/live-draft/${encodeURIComponent(draftId)}/trade-evaluator`,
    ),
  postLiveDraftTradeEvaluator: (
    leagueId: string,
    draftId: string,
    body: {
      sendPickKeys?: string[];
      receivePickKeys?: string[];
      sendPlayerIds?: string[];
      receivePlayerIds?: string[];
      lens?: string;
    },
  ) =>
    authorizedRequest<LiveDraftTradeEvaluatorResponse>(
      `/v1/leagues/${encodeURIComponent(leagueId)}/live-draft/${encodeURIComponent(draftId)}/trade-evaluator`,
      {
        method: "POST",
        jsonBody: {
          send_pick_keys: body.sendPickKeys ?? [],
          receive_pick_keys: body.receivePickKeys ?? [],
          send_player_ids: body.sendPlayerIds ?? [],
          receive_player_ids: body.receivePlayerIds ?? [],
          lens: body.lens ?? "Dynasty",
        },
      },
    ),
};
