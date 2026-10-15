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
};
