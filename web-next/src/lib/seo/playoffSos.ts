import { apiBases } from "./publicValues";

/**
 * Server-side client for GET /v1/public/playoff-sos: anonymous fantasy-playoff strength of
 * schedule (modules/public_playoff_sos.py, a public projection of the Phase 2 external endpoint).
 * Built from the nflverse schedule and recency-weighted points allowed by position. Never league data.
 */
export const SOS_POSITIONS = ["QB", "RB", "WR", "TE"] as const;
export type SosPosition = (typeof SOS_POSITIONS)[number];

export interface SosPositionRow {
  avg_points_allowed: number;
  vs_league_avg_pct: number;
  rank_easiest: number | null;
  of: number | null;
}

export interface SosOpponent {
  week: number;
  opponent: string | null;
  is_home: boolean | null;
}

export interface SosTeam {
  team: string;
  confidence: string | null;
  opponents: SosOpponent[];
  by_position: Partial<Record<SosPosition, SosPositionRow>>;
}

export interface PlayoffSos {
  status: "ok" | "unavailable";
  unavailable_reason: string | null;
  generated_at: string;
  season: number;
  weeks: number[];
  methodology: string;
  teams: SosTeam[];
}

function isTeam(value: unknown): value is SosTeam {
  if (!value || typeof value !== "object") return false;
  const t = value as Record<string, unknown>;
  return typeof t.team === "string" && Array.isArray(t.opponents) && !!t.by_position && typeof t.by_position === "object";
}

export function parsePlayoffSos(value: unknown): PlayoffSos | null {
  if (!value || typeof value !== "object") return null;
  const b = value as Record<string, unknown>;
  if (typeof b.generated_at !== "string" || typeof b.season !== "number" || !Array.isArray(b.weeks)) return null;
  const teams = Array.isArray(b.teams) ? b.teams.filter(isTeam) : [];
  return {
    status: b.status === "ok" && teams.length > 0 ? "ok" : "unavailable",
    unavailable_reason: typeof b.unavailable_reason === "string" ? b.unavailable_reason : null,
    generated_at: b.generated_at,
    season: b.season,
    weeks: (b.weeks as unknown[]).filter((w): w is number => typeof w === "number"),
    methodology: typeof b.methodology === "string" ? b.methodology : "",
    teams,
  };
}

/** Null on any transport failure so a page can render its honest "not available" state. */
export async function fetchPlayoffSos(): Promise<PlayoffSos | null> {
  for (const base of apiBases()) {
    try {
      const response = await fetch(`${base}/v1/public/playoff-sos`, {
        next: { revalidate: 3600 },
        signal: AbortSignal.timeout(8000),
      });
      if (!response.ok) continue;
      const parsed = parsePlayoffSos(await response.json());
      if (parsed) return parsed;
    } catch {
      // try the next base
    }
  }
  return null;
}

/** Teams for one position, easiest schedule first (rank_easiest 1 = most points allowed). */
export function rankedAt(sos: PlayoffSos, position: SosPosition): { team: SosTeam; row: SosPositionRow }[] {
  return sos.teams
    .flatMap((team) => {
      const row = team.by_position[position];
      return row && row.rank_easiest !== null ? [{ team, row }] : [];
    })
    .sort((a, b) => (a.row.rank_easiest as number) - (b.row.rank_easiest as number) || a.team.team.localeCompare(b.team.team));
}

/** "W15 vs DEN, W16 @LV, W17 BYE" */
export function scheduleLine(team: SosTeam): string {
  return team.opponents
    .map((o) => (o.opponent ? `W${o.week} ${o.is_home ? "vs" : "@"} ${o.opponent}` : `W${o.week} BYE`))
    .join(", ");
}

/** A page is only worth indexing with a near-full league of rated teams. */
export function hasUsableSos(sos: PlayoffSos | null): sos is PlayoffSos {
  return !!sos && sos.status === "ok" && sos.teams.length >= 16;
}
