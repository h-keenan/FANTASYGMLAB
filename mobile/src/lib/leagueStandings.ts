/**
 * The League Rankings Standings module, one definition for web and app (byte-identical lib twin): copy, title,
 * record text, order and the collapsed summary. The tie-break math is server-side
 * (modules.league_standings.build_league_standings_bundle); `standing_rank` is final, this only orders and words it.
 */

export const STANDINGS_NOTE = "Actual results from league matchups — separate from Roster Power strength.";
export const STANDINGS_KICKER = "Where you stand";
export const STANDINGS_EMPTY = "Standings will populate once regular-season results are available.";

export interface StandingTeam {
  roster_id: string;
  team_name: string | null;
  wins: number | null;
  losses: number | null;
  ties: number | null;
  standing_rank?: number | null;
}

export function standingsTitle(season: string | null | undefined): string {
  return season ? `${season} Standings` : "Standings";
}

export function standingRecord(team: Pick<StandingTeam, "wins" | "losses" | "ties">): string {
  return `${team.wins ?? 0}-${team.losses ?? 0}${team.ties ? `-${team.ties}` : ""}`;
}

export function sortByStanding<T extends { standing_rank?: number | null }>(teams: readonly T[]): T[] {
  return [...teams].sort((a, b) => (a.standing_rank ?? Number.MAX_SAFE_INTEGER) - (b.standing_rank ?? Number.MAX_SAFE_INTEGER));
}

export interface StandingsSummaryPart {
  key: string;
  text: string;
  strong?: boolean;
  tone?: "accent";
}

/** "1. Team 8-2 · You #3 · 5-5 · 12 teams". */
export function standingsSummaryParts<T extends StandingTeam>(ordered: readonly T[], myRosterId: string): StandingsSummaryPart[] {
  const first = ordered[0];
  const me = ordered.find((team) => team.roster_id === myRosterId);
  const parts: Array<StandingsSummaryPart | null> = [
    first ? { key: "first", text: `1. ${first.team_name || "Team"} ${standingRecord(first)}`, strong: true } : null,
    me && me.standing_rank != null ? { key: "you", text: `You #${Math.round(me.standing_rank)} · ${standingRecord(me)}`, tone: "accent" } : null,
    { key: "n", text: `${ordered.length} teams` },
  ];
  return parts.filter((part): part is StandingsSummaryPart => part != null);
}
