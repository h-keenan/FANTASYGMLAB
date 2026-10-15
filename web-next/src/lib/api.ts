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
  wins: number | null;
  losses: number | null;
  ties: number | null;
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
  archetype_label: string | null;
  archetype_strengths: string[];
}

export interface TeamRankingsResponse {
  ok: boolean;
  teams: TeamRanking[];
  reason: string;
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
    authorizedRequest<TeamRankingsResponse>(
      `/v1/leagues/${encodeURIComponent(leagueId)}/team-rankings?lens=${encodeURIComponent(lens)}`,
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
};
