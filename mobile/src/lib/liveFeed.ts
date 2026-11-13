/**
 * LIVE FEED: scoring events derived while the Matchup page is open by diffing
 * consecutive polled snapshots of each starter's points and stat line. Pure
 * and import-free; byte-identical twin of mobile/src/lib/liveFeed.ts.
 *
 * Honest by construction: Sleeper has no play-by-play, so an event is "what
 * changed between two polls", stamped with the poll time. When several things
 * changed in one poll the event is labeled `approx`. See
 * docs/live-plays-research.md.
 */

export type FeedSide = "mine" | "opponent";
export type StatLine = Record<string, number>;

/** The slice of a Matchup payload the feed reads (structural, so web and app types both fit). */
export interface FeedStarterLike {
  player_id: string;
  name?: string | null;
  position?: string | null;
  team?: string | null;
  actual_points?: number | null;
  game_started?: boolean | null;
  game_status?: string | null;
  game_opponent?: string | null;
  game_is_home?: boolean | null;
  game_team_score?: number | null;
  game_opponent_score?: number | null;
  game_progress?: number | null;
  stats?: StatLine | null;
}
export interface FeedMatchupLike {
  week?: number | null;
  game_state?: string | null;
  my_team?: { has_live_data?: boolean; real_starters?: FeedStarterLike[] } | null;
  opponent?: { has_live_data?: boolean; real_starters?: FeedStarterLike[] } | null;
}

export interface FeedPlayerSnapshot {
  playerId: string;
  name: string;
  position: string | null;
  team: string | null;
  side: FeedSide;
  points: number | null;
  stats: StatLine | null;
  gameKey: string;
  gameLabel: string;
  gameStatus: string | null;
  gameProgress: number | null;
  teamScore: number | null;
  opponentScore: number | null;
  isHome: boolean | null;
}
export type FeedSnapshot = Map<string, FeedPlayerSnapshot>;

export interface FeedEvent {
  id: string;
  /** Poll time (ms since epoch) the change was observed, not the play time. */
  at: number;
  playerId: string;
  name: string;
  position: string | null;
  team: string | null;
  side: FeedSide;
  /** Fantasy points gained (negative: a stat correction). */
  points: number;
  /** Plain-English detail, e.g. "rushing TD, 4 yds". */
  detail: string;
  /** Several things merged into one event, or the cause is inferred from points only. */
  approx: boolean;
  /** Touchdown / field goal / turnover (for emphasis). */
  major: boolean;
  gameKey: string;
  gameLabel: string;
}

export const MAX_FEED_EVENTS = 50;

const num = (value: unknown): number => (typeof value === "number" && Number.isFinite(value) ? value : 0);

function delta(prev: StatLine | null, next: StatLine, key: string): number {
  return num(next[key]) - num(prev?.[key]);
}

function yds(n: number): string {
  const rounded = Math.round(Math.abs(n));
  return `${rounded} yd${rounded === 1 ? "" : "s"}`;
}

interface StatPiece {
  text: string;
  major: boolean;
}

/** Human-readable pieces for what changed between two stat lines (TD, FG, INT, fumble, catches, rushes, defense). */
export function deriveStatPieces(prev: StatLine | null, next: StatLine | null): StatPiece[] {
  if (!next) return [];
  const d = (key: string) => delta(prev, next, key);
  const pieces: StatPiece[] = [];
  const times = (n: number, label: string) => (n > 1 ? `${n} ${label}s` : label);

  if (d("pass_td") > 0) pieces.push({ text: `${times(d("pass_td"), "passing TD")}${d("pass_yd") > 0 ? `, ${yds(d("pass_yd"))}` : ""}`, major: true });
  if (d("rush_td") > 0) pieces.push({ text: `${times(d("rush_td"), "rushing TD")}${d("rush_yd") !== 0 ? `, ${yds(d("rush_yd"))}` : ""}`, major: true });
  if (d("rec_td") > 0) pieces.push({ text: `${times(d("rec_td"), "receiving TD")}${d("rec_yd") !== 0 ? `, ${yds(d("rec_yd"))}` : ""}`, major: true });
  if (d("fgm") > 0) pieces.push({ text: times(d("fgm"), "field goal"), major: true });
  if (d("xpm") > 0) pieces.push({ text: times(d("xpm"), "extra point"), major: false });
  if (d("pass_int") > 0) pieces.push({ text: times(d("pass_int"), "interception thrown"), major: true });
  if (d("fum_lost") > 0) pieces.push({ text: times(d("fum_lost"), "fumble lost"), major: true });
  const twoPt = d("pass_2pt") + d("rush_2pt") + d("rec_2pt");
  if (twoPt > 0) pieces.push({ text: times(twoPt, "2-pt conversion"), major: false });
  if (d("def_td") > 0) pieces.push({ text: times(d("def_td"), "defensive TD"), major: true });
  if (d("int") > 0) pieces.push({ text: times(d("int"), "interception"), major: true });
  if (d("fum_rec") > 0) pieces.push({ text: times(d("fum_rec"), "fumble recovery"), major: true });
  if (d("sack") > 0) pieces.push({ text: times(Math.round(d("sack") * 10) / 10, "sack"), major: false });
  if (d("safe") > 0) pieces.push({ text: "safety", major: true });
  if (d("blk_kick") > 0) pieces.push({ text: "blocked kick", major: false });

  // Yardage-only plays, when no touchdown on that stat already described them.
  const hasRecTd = d("rec_td") > 0;
  const hasRushTd = d("rush_td") > 0;
  if (!hasRecTd && d("rec") > 0) pieces.push({ text: `${d("rec") > 1 ? `${d("rec")} catches` : "catch"}${d("rec_yd") !== 0 ? `, ${yds(d("rec_yd"))}` : ""}`, major: false });
  if (!hasRushTd && d("rush_att") > 0 && d("rush_yd") !== 0) pieces.push({ text: `${d("rush_att") > 1 ? `${d("rush_att")} rushes` : "rush"}, ${yds(d("rush_yd"))}`, major: false });
  if (d("pass_td") <= 0 && d("pass_cmp") > 0 && d("pass_yd") > 0) pieces.push({ text: `${d("pass_cmp") > 1 ? `${d("pass_cmp")} completions` : "completion"}, ${yds(d("pass_yd"))}`, major: false });
  return pieces;
}

function gameLabelFor(starter: FeedStarterLike): { key: string; label: string } {
  const team = (starter.team ?? "").trim();
  const opp = (starter.game_opponent ?? "").trim();
  if (!team) return { key: "other", label: "Other" };
  if (!opp) return { key: team, label: team };
  const away = starter.game_is_home === true ? opp : team;
  const home = starter.game_is_home === true ? team : opp;
  const pair = starter.game_is_home == null ? [team, opp].sort() : [away, home];
  return { key: [team, opp].sort().join("-"), label: `${pair[0]} @ ${pair[1]}` };
}

/** Snapshot of both teams' real starters; empty before games start. */
export function snapshotFromMatchup(matchup: FeedMatchupLike | null | undefined): FeedSnapshot {
  const out: FeedSnapshot = new Map();
  if (!matchup || matchup.game_state === "pregame" || matchup.game_state == null) return out;
  const add = (starters: FeedStarterLike[] | undefined, side: FeedSide) => {
    for (const starter of starters ?? []) {
      if (!starter.player_id) continue;
      const started = starter.game_started === true || starter.game_status === "in_progress" || starter.game_status === "final";
      const game = gameLabelFor(starter);
      out.set(`${side}:${starter.player_id}`, {
        playerId: starter.player_id,
        name: (starter.name ?? "").trim() || "Unknown player",
        position: starter.position ?? null,
        team: starter.team ?? null,
        side,
        points: started && typeof starter.actual_points === "number" ? starter.actual_points : null,
        stats: starter.stats ?? null,
        gameKey: game.key,
        gameLabel: game.label,
        gameStatus: starter.game_status ?? null,
        gameProgress: typeof starter.game_progress === "number" ? starter.game_progress : null,
        teamScore: typeof starter.game_team_score === "number" ? starter.game_team_score : null,
        opponentScore: typeof starter.game_opponent_score === "number" ? starter.game_opponent_score : null,
        isHome: typeof starter.game_is_home === "boolean" ? starter.game_is_home : null,
      });
    }
  };
  if (matchup.my_team?.has_live_data) add(matchup.my_team.real_starters, "mine");
  if (matchup.opponent?.has_live_data) add(matchup.opponent.real_starters, "opponent");
  return out;
}

const round1 = (n: number) => Math.round(n * 10) / 10;

/**
 * Events between two snapshots, one per player whose points or stat line
 * changed. No events on the first snapshot (nothing to diff against) and none
 * for a player who just entered the lineup.
 */
export function diffSnapshots(prev: FeedSnapshot | null, next: FeedSnapshot, at: number): FeedEvent[] {
  if (!prev || prev.size === 0) return [];
  const events: FeedEvent[] = [];
  for (const [key, now] of next) {
    const before = prev.get(key);
    if (!before || now.points == null || before.points == null) continue;
    const pointsDelta = round1(now.points - before.points);
    const pieces = deriveStatPieces(before.stats, now.stats);
    if (Math.abs(pointsDelta) < 0.05 && pieces.length === 0) continue;
    let detail: string;
    let approx: boolean;
    if (pointsDelta < -0.05 && pieces.length === 0) {
      detail = "scoring correction";
      approx = true;
    } else if (pieces.length === 0) {
      detail = "yardage / other scoring";
      approx = true;
    } else {
      detail = pieces.map((piece) => piece.text).join("; ");
      approx = pieces.length > 1;
    }
    events.push({
      id: `${at}:${key}`,
      at,
      playerId: now.playerId,
      name: now.name,
      position: now.position,
      team: now.team,
      side: now.side,
      points: pointsDelta,
      detail,
      approx,
      major: pieces.some((piece) => piece.major),
      gameKey: now.gameKey,
      gameLabel: now.gameLabel,
    });
  }
  // Biggest swing first within one poll.
  return events.sort((a, b) => Math.abs(b.points) - Math.abs(a.points));
}

/** Newest first, capped. */
export function mergeFeed(existing: FeedEvent[], fresh: FeedEvent[], max = MAX_FEED_EVENTS): FeedEvent[] {
  if (fresh.length === 0) return existing;
  const seen = new Set(existing.map((event) => event.id));
  const added = fresh.filter((event) => !seen.has(event.id));
  return [...added, ...existing].sort((a, b) => b.at - a.at).slice(0, max);
}

export interface FeedGame {
  key: string;
  label: string;
  /** "LIVE ~Q3", "Final 24-17" or null. */
  status: string | null;
  events: FeedEvent[];
}

function gameStatusText(snap: FeedPlayerSnapshot | undefined): string | null {
  if (!snap) return null;
  if (snap.gameStatus === "final") {
    return snap.teamScore != null && snap.opponentScore != null
      ? `Final ${Math.round(snap.teamScore)}-${Math.round(snap.opponentScore)}`
      : "Final";
  }
  if (snap.gameStatus === "in_progress") {
    const q = snap.gameProgress == null ? null : Math.min(4, Math.max(1, Math.ceil(snap.gameProgress * 4)));
    return q ? `Live ~Q${q}` : "Live";
  }
  return null;
}

/** Group events by NFL game (latest-active game first); status comes from the current snapshot. */
export function groupFeedByGame(events: FeedEvent[], snapshot: FeedSnapshot | null): FeedGame[] {
  const byKey = new Map<string, FeedGame>();
  for (const event of events) {
    let game = byKey.get(event.gameKey);
    if (!game) {
      const snap = snapshot ? [...snapshot.values()].find((p) => p.gameKey === event.gameKey) : undefined;
      game = { key: event.gameKey, label: event.gameLabel, status: gameStatusText(snap), events: [] };
      byKey.set(event.gameKey, game);
    }
    game.events.push(event);
  }
  return [...byKey.values()];
}

// ---- in-memory store, one feed per matchup (league + week), shared by both users of the page session ----

interface FeedEntry {
  snapshot: FeedSnapshot | null;
  events: FeedEvent[];
  version: number;
}
const entries = new Map<string, FeedEntry>();
const listeners = new Set<() => void>();
const EMPTY: FeedEvent[] = [];

export const liveFeedStore = {
  /** Feed one polled payload in; returns the events it produced. */
  ingest(key: string, matchup: FeedMatchupLike | null | undefined, at: number): FeedEvent[] {
    const next = snapshotFromMatchup(matchup);
    const entry = entries.get(key) ?? { snapshot: null, events: [], version: 0 };
    const fresh = diffSnapshots(entry.snapshot, next, at);
    entries.set(key, {
      snapshot: next.size > 0 ? next : entry.snapshot,
      events: mergeFeed(entry.events, fresh),
      version: entry.version + (fresh.length > 0 ? 1 : 0),
    });
    if (fresh.length > 0) listeners.forEach((listener) => listener());
    return fresh;
  },
  events(key: string): FeedEvent[] {
    return entries.get(key)?.events ?? EMPTY;
  },
  snapshot(key: string): FeedSnapshot | null {
    return entries.get(key)?.snapshot ?? null;
  },
  subscribe(listener: () => void): () => void {
    listeners.add(listener);
    return () => {
      listeners.delete(listener);
    };
  },
  reset(): void {
    entries.clear();
    listeners.forEach((listener) => listener());
  },
};

export function feedKey(leagueId: string, week: number | null | undefined): string {
  return `${leagueId}:${week ?? "?"}`;
}

/** "12s ago" / "3m ago" / clock time after an hour, for a feed item. */
export function feedAgeLabel(at: number, now: number): string {
  const seconds = Math.max(0, Math.round((now - at) / 1000));
  if (seconds < 10) return "just now";
  if (seconds < 60) return `${seconds}s ago`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  return `${Math.floor(seconds / 3600)}h ago`;
}

/** "+6.0" / "-1.5". */
export function feedPointsLabel(points: number): string {
  const rounded = round1(points);
  return `${rounded > 0 ? "+" : ""}${rounded.toFixed(1)}`;
}
