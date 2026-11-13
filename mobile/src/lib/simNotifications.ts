// Twin file: web-next/src/lib/simNotifications.ts and mobile/src/lib/simNotifications.ts stay identical.
//
// The Fantasy Sim notification center (the bell): types of GET /v1/sim/games/{id}/notifications, grouping by week,
// the unread logic against the client-held read cursor, and where an item deep-links. Pure (no React, no storage).

export interface SimNotificationTarget {
  screen: "trades" | "team" | "home" | "players" | "league" | "draft";
  player_id?: string;
  offer_id?: string;
}

export interface SimNotification {
  id: string;
  /** The event-log sequence it came from (or a stable synthetic one for state-derived items); newest first. */
  seq: number;
  week: number;
  kind: string;
  /** A Fantasy Sim glyph name (SimGlyph). */
  icon: string;
  headline: string;
  target: SimNotificationTarget;
}

export interface SimNotificationsResponse {
  ok?: boolean;
  reason?: string;
  items?: SimNotification[];
  unread?: number;
  seq?: number;
}

export type SimNotifTab = "home" | "team" | "players" | "trades" | "league";

/** Unread = items newer than the read cursor. */
export function simNotifUnread(items: readonly SimNotification[], cursor: number): number {
  return items.reduce((n, item) => n + (item.seq > cursor ? 1 : 0), 0);
}

/** The new cursor when everything is read: the response's latest seq (never moves backwards). */
export function simNotifMarkAllRead(cursor: number, latestSeq: number): number {
  return Math.max(cursor, latestSeq);
}

/** Badge text: "" for none, "9+" past nine. */
export function simNotifBadge(unread: number): string {
  if (unread <= 0) return "";
  return unread > 9 ? "9+" : String(unread);
}

export interface SimNotifGroup {
  week: number;
  label: string;
  items: SimNotification[];
}

/** Items grouped by week, newest week first, newest first inside a group. Week 0 is the draft. */
export function simNotifGroups(items: readonly SimNotification[]): SimNotifGroup[] {
  const byWeek = new Map<number, SimNotification[]>();
  for (const item of [...items].sort((a, b) => b.seq - a.seq)) {
    const list = byWeek.get(item.week) ?? [];
    list.push(item);
    byWeek.set(item.week, list);
  }
  return [...byWeek.entries()]
    .sort((a, b) => b[0] - a[0])
    .map(([week, list]) => ({ week, label: week === 0 ? "Draft" : `Week ${week}`, items: list }));
}

/** The short time label on a row: "Wk 7" (the draft is "Draft"). */
export function simNotifTime(item: Pick<SimNotification, "week">): string {
  return item.week === 0 ? "Draft" : `Wk ${item.week}`;
}

/** Which tab an item opens (the draft lives on Home while it is on). */
export function simNotifTargetTab(target: SimNotificationTarget): SimNotifTab {
  switch (target.screen) {
    case "trades":
    case "team":
    case "players":
    case "league":
      return target.screen;
    default:
      return "home";
  }
}

/**
 * The refetch key: the bell reloads only when the game itself changed (week, phase, inbox, lineup warnings, claims),
 * never on a timer. Equal keys mean "no new data possible".
 */
export function simNotifKey(game: { status?: string; week?: number; pending?: { inbox?: number; lineup_warnings?: number; claims?: number } | null }, tick = 0): string {
  const p = game.pending;
  return [game.status ?? "", game.week ?? "", p?.inbox ?? 0, p?.lineup_warnings ?? 0, p?.claims ?? 0, tick].join("|");
}

/** localStorage / AsyncStorage key of a game's read cursor. */
export function simNotifCursorKey(gameId: string): string {
  return `fgl:sim-notif-read:${gameId}`;
}

export function simNotifParseCursor(raw: string | null | undefined): number {
  const n = Number(raw);
  return Number.isFinite(n) && n > 0 ? Math.floor(n) : 0;
}
