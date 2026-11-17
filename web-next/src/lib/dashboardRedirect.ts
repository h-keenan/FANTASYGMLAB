import { leagueHomePath } from "@/lib/leaguePlatform";

export interface SavedLeagueRef {
  league_id: string;
  league_name: string | null;
}

/**
 * Where a bare /dashboard (no league id) goes: signed out -> the landing page; no saved league -> the connect-league
 * flow; one league -> its home; several -> the last-opened league when still saved, else the first.
 */
export function dashboardRedirectTarget(
  signedIn: boolean,
  leagues: readonly SavedLeagueRef[],
  lastLeagueId: string | null,
): string {
  if (!signedIn) return "/";
  if (leagues.length === 0) return "/connect-league";
  const pick = leagues.find((l) => l.league_id === lastLeagueId) ?? leagues[0];
  return leagueHomePath(pick.league_id, pick.league_name || pick.league_id);
}
