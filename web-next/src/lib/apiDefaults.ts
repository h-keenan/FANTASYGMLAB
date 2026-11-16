/**
 * Response normalizers: the one place a missing or null field in an API
 * payload becomes a safe default (empty array / object / zero), so a partial
 * or drifted response renders an empty state instead of throwing
 * (`undefined.map`) and blanking the page. api.ts applies these at the fetch
 * boundary; components keep trusting the declared types.
 * Byte-identical to mobile/src/lib/apiDefaults.ts (twin test).
 */
import type { CollegeProspect, CollegeProspectsResponse, CommunityTradeItem, CommunityTradesResponse, LeagueRankingsResponse, LeagueRostersResponse, LeagueTeamProfilesResponse, MeResponse, SharedCommunityTradesResponse } from "./api";
import type { CommissionerIntegrityResponse } from "./commissionerIntegrity";

type Rec = Record<string, unknown>;

/** The value when it is a real array, else []. */
export function arr<T>(v: unknown): T[] {
  return Array.isArray(v) ? (v as T[]) : [];
}

/** The value when it is a plain object, else {}. */
export function rec(v: unknown): Rec {
  return v !== null && typeof v === "object" && !Array.isArray(v) ? (v as Rec) : {};
}

/** Array of plain objects only (drops null / primitive rows). */
function rows<T>(v: unknown): T[] {
  return arr<unknown>(v).filter((x) => x !== null && typeof x === "object") as T[];
}

export function normalizeCommissionerIntegrity(raw: unknown): CommissionerIntegrityResponse {
  const r = rec(raw);
  return {
    ...r,
    ok: r.ok === true,
    reason: typeof r.reason === "string" ? r.reason : "",
    teams: rows(r.teams),
    collusion: rows(r.collusion),
    inactive: rows(r.inactive),
    limits: arr<string>(r.limits),
  } as CommissionerIntegrityResponse;
}

function normalizeProspect(raw: Rec): CollegeProspect {
  const agg = rec(raw.aggregate);
  return {
    ...raw,
    aggregate: {
      avg_grade: typeof agg.avg_grade === "number" ? agg.avg_grade : null,
      scout_count: typeof agg.scout_count === "number" ? agg.scout_count : 0,
      avg_round_projection: typeof agg.avg_round_projection === "number" ? agg.avg_round_projection : null,
    },
    my_report: raw.my_report && typeof raw.my_report === "object" ? raw.my_report : null,
    on_watchlist: raw.on_watchlist === true,
  } as CollegeProspect;
}

export function normalizeCollegeProspects(raw: unknown): CollegeProspectsResponse {
  const r = rec(raw);
  return {
    ...r,
    ok: r.ok === true,
    prospects: rows<Rec>(r.prospects).map(normalizeProspect),
    catalog_available: r.catalog_available === true,
    reason: typeof r.reason === "string" ? r.reason : "",
  } as CollegeProspectsResponse;
}

function normalizeCommunityTrade(raw: Rec): CommunityTradeItem {
  return {
    ...raw,
    send: rows(raw.send),
    receive: rows(raw.receive),
    reactions: rec(raw.reactions),
    my_reactions: arr<string>(raw.my_reactions),
  } as unknown as CommunityTradeItem;
}

export function normalizeCommunityTrades(raw: unknown): CommunityTradesResponse {
  const r = rec(raw);
  return {
    ...r,
    ok: r.ok === true,
    trades: rows<Rec>(r.trades).map(normalizeCommunityTrade),
    reaction_emoji: arr<string>(r.reaction_emoji),
  } as CommunityTradesResponse;
}

export function normalizeSharedCommunityTrades(raw: unknown): SharedCommunityTradesResponse {
  const r = rec(raw);
  return {
    ...r,
    ok: r.ok === true,
    available: r.available === true,
    trades: rows<Rec>(r.trades).map((t) => ({ ...t, send: rows(t.send), receive: rows(t.receive) })),
  } as unknown as SharedCommunityTradesResponse;
}

export function normalizeLeagueRosters(raw: unknown): LeagueRostersResponse {
  const r = rec(raw);
  return { ...r, ok: r.ok === true, rosters: rows(r.rosters) } as LeagueRostersResponse;
}

export function normalizeLeagueTeamProfiles(raw: unknown): LeagueTeamProfilesResponse {
  const r = rec(raw);
  return { ...r, ok: r.ok === true, profiles: rec(r.profiles) } as unknown as LeagueTeamProfilesResponse;
}

export function normalizeLeagueRankings(raw: unknown): LeagueRankingsResponse {
  const r = rec(raw);
  return { ...r, ok: r.ok === true, players: rows(r.players) } as LeagueRankingsResponse;
}

/** A missing user reads as a signed-in Free account with an errored profile lookup (the fail-closed default the server itself uses). */
export function normalizeMe(raw: unknown): MeResponse {
  const r = rec(raw);
  const u = rec(r.user);
  const str = (v: unknown) => (typeof v === "string" ? v : "");
  return {
    ...r,
    ok: true,
    user: {
      ...u,
      id: str(u.id),
      email: str(u.email),
      entitlement: u.entitlement === "premium" ? "premium" : "free",
      sleeper_username: str(u.sleeper_username),
      profile_status: u.profile_status === "ok" ? "ok" : "error",
      league_cap: typeof u.league_cap === "number" ? u.league_cap : 1,
    },
    premium_benefits: arr<string>(r.premium_benefits),
  } as unknown as MeResponse;
}
