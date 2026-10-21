// Mirrors the fields of SleeperLeagueOption (./api) this module actually
// uses. Defined locally (rather than importing from ./api) so this stays a
// plain-node-testable module, like leaguesGlance.ts's own local types --
// ./api pulls in react-native at module scope.
export interface SeasonGroupableLeague {
  league_id: string;
  name: string;
  season: string;
  total_rosters: number;
}

export interface LeagueSeasonGroup {
  title: string;
  data: SeasonGroupableLeague[];
}

/**
 * Groups Sleeper league-lookup options by season, most recent season
 * first, for SectionList rendering.
 *
 * Bug report, 2026-10-21: "it keeps auto defaulting to 2025" / "we need to
 * be able to separate by year" -- a continuing dynasty league gets a
 * brand-new league_id every season it rolls over on Sleeper's side
 * (modules/sleeper_leagues.py queries both the current and previous
 * season and merges them), so the SAME league can legitimately appear in
 * this list twice, once per season. A flat list made it easy to tap the
 * wrong year's row for "the same" league. Grouping by season under a
 * visible year header makes the distinction impossible to miss.
 */
export function groupLeagueOptionsBySeason(
  options: SeasonGroupableLeague[] | null | undefined,
): LeagueSeasonGroup[] {
  const groups = new Map<string, SeasonGroupableLeague[]>();
  for (const option of options ?? []) {
    const season = option.season || 'Unknown';
    const existing = groups.get(season);
    if (existing) {
      existing.push(option);
    } else {
      groups.set(season, [option]);
    }
  }

  const titles = Array.from(groups.keys()).sort((a, b) => {
    const numA = Number(a);
    const numB = Number(b);
    const aIsNum = Number.isFinite(numA);
    const bIsNum = Number.isFinite(numB);
    if (aIsNum && bIsNum) return numB - numA;
    if (aIsNum) return -1;
    if (bIsNum) return 1;
    return a.localeCompare(b);
  });

  return titles.map((title) => ({ title, data: groups.get(title) ?? [] }));
}
