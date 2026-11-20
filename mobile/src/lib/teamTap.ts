// Shared (web + mobile twin, byte-identical, import-free): the tap rule every league team name / avatar follows.
// A team shown anywhere inside a league opens the shared team sheet (ManagerProfileSheet / ManagerProfileModal) on tap,
// through the one TeamNameLink component. A name stays plain only when there is nothing to open (no league or roster id,
// e.g. a sample row or a Fantasy Sim team) or when the screen is already that team's own page (`current`), where the
// tap would be a no-op. Your own team elsewhere IS a link: the sheet shows your team's record, roster and needs.

export interface TapTeam {
  leagueId?: string | null;
  rosterId?: string | number | null;
  name?: string | null;
}

/** A team can open the sheet when both the league and the roster are known. */
export function canOpenTeam(team: TapTeam | null | undefined): boolean {
  if (!team) return false;
  const hasLeague = team.leagueId != null && String(team.leagueId).length > 0;
  const hasRoster = team.rosterId != null && String(team.rosterId).length > 0;
  return hasLeague && hasRoster;
}

/** The link only renders as a tap target when it can open and is not already on that team's own page. */
export function teamLinkInteractive(team: TapTeam | null | undefined, current?: boolean): boolean {
  return canOpenTeam(team) && !current;
}

/** Screen-reader name of a team tap target; matches the long-standing "team sheet" wording of the trade card button. */
export function teamOpenLabel(name: string | null | undefined): string {
  const shown = (name ?? "").trim();
  return shown ? `Open ${shown} team sheet` : "Open team sheet";
}

/** The name shown when a team has none. */
export function teamDisplayName(name: string | null | undefined): string {
  const shown = (name ?? "").trim();
  return shown || "Team";
}

/** Minimum tap target (px) for a team name / avatar tap area. */
export const TEAM_TAP_MIN = 44;
