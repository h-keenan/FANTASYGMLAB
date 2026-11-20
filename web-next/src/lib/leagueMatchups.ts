/**
 * The League page's Matchups section (every pair of a week in a real Sleeper league), one definition for web and app
 * (import-free, byte-identical lib twin). The server (GET .../matchups, modules/league_matchups.py) computes live
 * points, blended projected totals and win chance with the same code as the Matchup page; this only words and tones them.
 * Tone rule: the leading side is green, the trailing side is the muted tone, never red.
 */

export type LeagueMatchupTone = "leader" | "trailing" | "even";
export type LeagueMatchupState = "live" | "final" | "pregame" | "between_games" | null;

export interface LeagueMatchupSideView {
  roster_id: string;
  team_name: string;
  owner_name: string;
  avatar_url: string;
  record_label: string;
  streak: number;
  streak_label: string;
  standing_rank: number | null;
  points: number | null;
  projected_total: number | null;
  /** 0-1, this side's chance to win; null when not modeled yet. */
  win_probability: number | null;
  is_mine: boolean;
}

export interface LeagueMatchupPairView {
  matchup_id: number | string;
  game_state: LeagueMatchupState;
  sides: LeagueMatchupSideView[];
}

export const LEAGUE_MATCHUPS_TITLE = "Matchups";
export const LEAGUE_MATCHUPS_MAX_WEEK = 18;

/** "Wk 1" .. "Wk N" for the week select: 1..max, left to right. */
export function leagueMatchupWeeks(maxWeek: number): number[] {
  return Array.from({ length: Math.max(0, Math.floor(maxWeek)) }, (_, i) => i + 1);
}

export function formatMatchupPoints(points: number | null | undefined): string {
  return typeof points === "number" && Number.isFinite(points) ? points.toFixed(1) : "—";
}

export function formatMatchupProjected(total: number | null | undefined): string | null {
  return typeof total === "number" && Number.isFinite(total) ? `Proj ${total.toFixed(1)}` : null;
}

/** Win chance as a whole percent (0-100), or null when not modeled. */
export function winPercent(probability: number | null | undefined): number | null {
  if (typeof probability !== "number" || !Number.isFinite(probability)) return null;
  return Math.max(0, Math.min(100, Math.round(probability * 100)));
}

/**
 * Who leads a pair: by win chance when modeled, else by points once any are on the board, else even. Ties are even.
 * Returns each side's tone in order.
 */
export function pairTones(pair: LeagueMatchupPairView): [LeagueMatchupTone, LeagueMatchupTone] {
  const [a, b] = pair.sides;
  if (!a || !b) return ["even", "even"];
  const pa = winPercent(a.win_probability);
  const pb = winPercent(b.win_probability);
  if (pa !== null && pb !== null && pa !== pb) return pa > pb ? ["leader", "trailing"] : ["trailing", "leader"];
  if (pa !== null && pb !== null) return ["even", "even"];
  const sa = a.points;
  const sb = b.points;
  if (sa != null && sb != null && sa !== sb) return sa > sb ? ["leader", "trailing"] : ["trailing", "leader"];
  return ["even", "even"];
}

/** The two win-bar widths (percent, sum 100). An unmodeled pair splits evenly, drawn muted by the caller. */
export function winBarSplit(pair: LeagueMatchupPairView): [number, number] {
  const [a, b] = pair.sides;
  const pa = winPercent(a?.win_probability);
  if (pa === null || !b) return [50, 50];
  return [pa, 100 - pa];
}

export function matchupStateLabel(state: LeagueMatchupState | undefined): string {
  if (state === "live") return "Live";
  if (state === "final") return "Final";
  if (state === "pregame") return "Upcoming";
  if (state === "between_games") return "In progress";
  return "Upcoming";
}

/** "#2 · 5-2 · ▲3W": standing, record and streak, dropping what is unknown. */
export function sideSubline(side: Pick<LeagueMatchupSideView, "standing_rank" | "record_label" | "streak_label">): string {
  return [side.standing_rank ? `#${side.standing_rank}` : "", side.record_label, side.streak_label].filter(Boolean).join(" · ");
}

/** Screen-reader sentence for one card. */
export function pairAriaLabel(pair: LeagueMatchupPairView): string {
  const [a, b] = pair.sides;
  if (!a || !b) return "Matchup";
  const part = (s: LeagueMatchupSideView) => {
    const pct = winPercent(s.win_probability);
    return `${s.team_name} ${formatMatchupPoints(s.points)}${pct !== null ? `, ${pct} percent to win` : ""}`;
  };
  return `${matchupStateLabel(pair.game_state)}: ${part(a)} versus ${part(b)}`;
}

export interface LeagueMatchupsPart {
  key: string;
  text: string;
  strong?: boolean;
  tone?: "success" | "muted" | "accent";
}

/** The collapsed section summary: "Wk 11 · 6 matchups · 2 live · You 98.2-84.1 (71%)". */
export function leagueMatchupsSummaryParts(week: number | null, pairs: readonly LeagueMatchupPairView[]): LeagueMatchupsPart[] {
  if (!week) return [{ key: "none", text: "Not available yet", tone: "muted" }];
  const parts: LeagueMatchupsPart[] = [{ key: "week", text: `Wk ${week}`, strong: true }];
  if (pairs.length === 0) return [...parts, { key: "empty", text: "No matchups yet", tone: "muted" }];
  parts.push({ key: "count", text: `${pairs.length} ${pairs.length === 1 ? "matchup" : "matchups"}` });
  const live = pairs.filter((p) => p.game_state === "live").length;
  if (live > 0) parts.push({ key: "live", text: `${live} live`, tone: "success" });
  const mine = pairs.find((p) => p.sides.some((s) => s.is_mine));
  if (mine) {
    const me = mine.sides.find((s) => s.is_mine);
    const them = mine.sides.find((s) => !s.is_mine);
    if (me && them && (me.points != null || them.points != null)) {
      const pct = winPercent(me.win_probability);
      parts.push({ key: "mine", text: `You ${formatMatchupPoints(me.points)}-${formatMatchupPoints(them.points)}${pct !== null ? ` (${pct}%)` : ""}`, tone: "accent" });
    }
  }
  return parts;
}

/** The week the section opens on: the league's current week, else the last one. */
export function defaultMatchupWeek(currentWeek: number | null | undefined, maxWeek: number = LEAGUE_MATCHUPS_MAX_WEEK): number | null {
  if (!currentWeek || currentWeek < 1) return null;
  return Math.min(Math.floor(currentWeek), maxWeek);
}

/** Server reasons that mean "this league has no matchups list": the section stays hidden instead of an empty module. */
export function leagueMatchupsHidden(reason: string | null | undefined): boolean {
  return reason === "unsupported_platform" || reason === "no_current_week" || reason === "no_player_data";
}
