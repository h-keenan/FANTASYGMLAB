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
  init?: { method?: 'GET' | 'POST'; jsonBody?: unknown },
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

export interface MeResponse {
  ok: true;
  user: {
    id: string;
    email: string;
    entitlement: 'free' | 'premium';
    sleeper_username: string;
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
}

export interface LeagueRankingsResponse {
  ok: true;
  players: RankedPlayer[];
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

export type TeamStrategy =
  | 'contender'
  | 'fringe_contender'
  | 'retool'
  | 'rebuild'
  | 'tank';

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
  getMyRoster: (leagueId: string) =>
    authorizedFetch<MyRosterResponse>(`/v1/leagues/${encodeURIComponent(leagueId)}/my-roster`),
  getLeagueRankings: (leagueId: string, options?: { lens?: ValuationLens; limit?: number }) => {
    const params = new URLSearchParams();
    if (options?.lens) params.set('lens', options.lens);
    params.set('limit', String(options?.limit ?? 300));
    return authorizedFetch<LeagueRankingsResponse>(
      `/v1/leagues/${encodeURIComponent(leagueId)}/rankings?${params.toString()}`,
    );
  },
  getNews: (limit = 30) => authorizedFetch<NewsResponse>(`/v1/news?limit=${limit}`),
  postTradeAnalyzer: (
    leagueId: string,
    body: {
      sendPlayerIds: string[];
      receivePlayerIds: string[];
      strategy?: TeamStrategy;
      lens?: ValuationLens;
    },
  ) =>
    authorizedPost<TradeAnalyzerResponse>(`/v1/leagues/${encodeURIComponent(leagueId)}/trade-analyzer`, {
      send_player_ids: body.sendPlayerIds,
      receive_player_ids: body.receivePlayerIds,
      strategy: body.strategy ?? 'retool',
      lens: body.lens ?? 'Dynasty',
    }),
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
};
