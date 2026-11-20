/**
 * Live sections of the top Matchup module: the games in progress (real clock) and one merged play list
 * (server big plays + plays derived by the client feed). Pure and import-free; byte-identical twin of
 * mobile/src/lib/matchupLive.ts.
 */

export interface LiveStarterLike {
  team?: string | null;
  game_status?: string | null;
  game_clock_label?: string | null;
  game_situation?: string | null;
  game_opponent?: string | null;
  game_is_home?: boolean | null;
  game_team_score?: number | null;
  game_opponent_score?: number | null;
}

export interface LiveGame {
  key: string;
  /** "HOU 14 - 3 IND" */
  score: string;
  /** "Q2 5:54", "Half", "Final" */
  clock: string | null;
  /** "2nd & 7 at HOU 25" (only while live and the source provides it). */
  situation: string | null;
  live: boolean;
}

/** One row per NFL game any of the starters is in, live games first. Not-started games are left out. */
export function liveGamesFromStarters(starters: LiveStarterLike[]): LiveGame[] {
  const seen = new Map<string, LiveGame>();
  for (const starter of starters) {
    const status = starter.game_status;
    if (status !== "in_progress" && status !== "final") continue;
    const team = (starter.team ?? "").toUpperCase();
    const opponent = (starter.game_opponent ?? "").toUpperCase();
    if (!team || !opponent) continue;
    const key = [team, opponent].sort().join("-");
    if (seen.has(key)) continue;
    const mineScore = starter.game_team_score;
    const oppScore = starter.game_opponent_score;
    const hasScore = typeof mineScore === "number" && typeof oppScore === "number";
    const [home, away] = starter.game_is_home === false ? [opponent, team] : [team, opponent];
    const homeScore = starter.game_is_home === false ? oppScore : mineScore;
    const awayScore = starter.game_is_home === false ? mineScore : oppScore;
    seen.set(key, {
      key,
      score: hasScore ? `${away} ${Math.round(awayScore as number)} - ${Math.round(homeScore as number)} ${home}` : `${away} @ ${home}`,
      clock: starter.game_clock_label ?? (status === "final" ? "Final" : null),
      situation: status === "in_progress" ? (starter.game_situation ?? null) : null,
      live: status === "in_progress",
    });
  }
  return [...seen.values()].sort((a, b) => Number(b.live) - Number(a.live));
}

export interface ServerPlayLike {
  id: string;
  at: number;
  player_id?: string | null;
  name: string;
  side: "mine" | "opponent";
  points: number;
  description: string;
  approx?: boolean;
  clock?: string | null;
  so_far?: boolean;
}

export interface ClientPlayLike {
  id: string;
  at: number;
  playerId: string;
  name: string;
  side: "mine" | "opponent";
  points: number;
  detail: string;
  approx: boolean;
}

export interface LivePlay {
  id: string;
  at: number;
  playerId: string | null;
  name: string;
  side: "mine" | "opponent";
  points: number;
  detail: string;
  approx: boolean;
  clock: string | null;
  soFar: boolean;
}

export const MAX_LIVE_PLAYS = 6;

/** Server plays plus plays the client derived between polls, newest first, one row per player + points swing. */
export function mergeLivePlays(server: ServerPlayLike[] | null | undefined, client: ClientPlayLike[] | null | undefined): LivePlay[] {
  const rows: LivePlay[] = [];
  const seen = new Set<string>();
  const push = (row: LivePlay) => {
    const key = `${row.playerId ?? row.name}:${row.points.toFixed(1)}`;
    if (seen.has(key)) return;
    seen.add(key);
    rows.push(row);
  };
  for (const p of server ?? []) {
    push({ id: p.id, at: p.at, playerId: p.player_id ?? null, name: p.name, side: p.side, points: p.points, detail: p.description, approx: Boolean(p.approx), clock: p.clock ?? null, soFar: Boolean(p.so_far) });
  }
  for (const p of client ?? []) {
    push({ id: p.id, at: p.at, playerId: p.playerId, name: p.name, side: p.side, points: p.points, detail: p.detail, approx: p.approx, clock: null, soFar: false });
  }
  // "so far" lines are context, not events: they sort under real plays.
  return rows.sort((a, b) => Number(a.soFar) - Number(b.soFar) || b.at - a.at).slice(0, MAX_LIVE_PLAYS);
}

/** "All quiet · last checked 12s ago" (or just "All quiet" before the first poll); `ageSeconds` is the data age. */
export function quietLabel(ageSeconds: number | null | undefined): string {
  if (ageSeconds == null || !Number.isFinite(ageSeconds)) return "All quiet";
  const seconds = Math.max(0, Math.round(ageSeconds));
  return `All quiet · last checked ${seconds < 60 ? `${seconds}s` : `${Math.round(seconds / 60)}m`} ago`;
}
