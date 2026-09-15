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

async function authorizedFetch<T>(path: string): Promise<T> {
  const { data, error: sessionError } = await supabase.auth.getSession();
  if (sessionError || !data.session) {
    throw new ApiError(401, 'Not signed in.');
  }

  const response = await fetch(`${env.apiBaseUrl}${path}`, {
    headers: {
      Authorization: `Bearer ${data.session.access_token}`,
    },
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

export interface MeResponse {
  ok: true;
  user: {
    id: string;
    email: string;
    entitlement: 'free' | 'premium';
  };
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
