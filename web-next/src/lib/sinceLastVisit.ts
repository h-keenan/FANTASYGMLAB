/**
 * "Since your last visit" on the web Dashboard: what actually happened in the
 * league while the person was away, from real data only (league transactions
 * from History, news/injuries on rostered players from Alerts). The app's own
 * "Since your last check-in" diffs recommendation ids instead; this is the
 * web counterpart of the same job (UX audit 2026-11-03, 4.1: "Web has no
 * what changed").
 *
 * The last-visit timestamp is per user and per league, in localStorage like
 * the Start here card (`fd:start-here:v1:<user>`): best effort, never
 * required, nothing sent anywhere and no analytics event.
 */
import type { AlertItem, HistoryTransaction } from "./api";

/** A visit older than this counts as a new "session": the baseline moves up
 * to the previous visit, so a quick refresh does not blank the strip. */
export const NEW_VISIT_GAP_MS = 30 * 60 * 1000;
/** Ignore baselines older than this, so a long absence reads "last 14 days". */
export const MAX_LOOKBACK_MS = 14 * 24 * 60 * 60 * 1000;

export interface LastVisitState {
  /** Epoch ms: show what changed after this. */
  since: number;
  /** Epoch ms of the most recent visit. */
  last: number;
}

export function lastVisitStorageKey(userId: string, leagueId: string): string {
  return `fd:last-visit:v1:${userId}:${leagueId}`;
}

export function parseLastVisit(raw: string | null | undefined): LastVisitState | null {
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as Partial<LastVisitState> | null;
    if (typeof parsed?.since === "number" && typeof parsed?.last === "number" && parsed.since > 0 && parsed.last > 0) {
      return { since: parsed.since, last: parsed.last };
    }
  } catch {
    // fall through
  }
  return null;
}

/**
 * Pure state step for one Dashboard visit at `now`.
 * - First ever visit: nothing to compare yet; start the clock.
 * - A visit within NEW_VISIT_GAP_MS of the last one is the same sitting:
 *   keep the baseline.
 * - Otherwise the baseline becomes the previous visit.
 * `display` is the baseline to summarise from, or null on a first visit.
 */
export function advanceLastVisit(
  prev: LastVisitState | null,
  now: number,
): { next: LastVisitState; display: number | null } {
  if (!prev) return { next: { since: now, last: now }, display: null };
  const sameSitting = now - prev.last < NEW_VISIT_GAP_MS;
  const since = sameSitting ? prev.since : prev.last;
  return { next: { since, last: now }, display: Math.max(since, now - MAX_LOOKBACK_MS) };
}

export type SinceKey = "trades" | "claims" | "news";

export interface SinceItem {
  key: SinceKey;
  label: string;
  value: string;
  segment: "league-recaps" | "alerts";
}

/** Sleeper timestamps are epoch ms; tolerate seconds. */
function toMs(timestamp: number): number {
  return timestamp > 1e11 ? timestamp : timestamp * 1000;
}

const plural = (count: number, one: string, many: string) => `${count} ${count === 1 ? one : many}`;

export function buildSinceItems({
  transactions,
  alerts,
  sinceMs,
}: {
  transactions: HistoryTransaction[];
  alerts: AlertItem[];
  sinceMs: number;
}): SinceItem[] {
  const items: SinceItem[] = [];
  const recent = transactions.filter((tx) => tx.timestamp > 0 && toMs(tx.timestamp) > sinceMs);
  const trades = recent.filter((tx) => tx.type === "trade").length;
  const claims = recent.filter((tx) => tx.type === "waiver" || tx.type === "free_agent").length;
  if (trades > 0) items.push({ key: "trades", label: "New trades", value: `${plural(trades, "trade", "trades")} in your league`, segment: "league-recaps" });
  if (claims > 0) items.push({ key: "claims", label: "Waiver activity", value: `${plural(claims, "add or claim", "adds and claims")} in your league`, segment: "league-recaps" });

  const news = alerts.filter((alert) => alert.published_ts != null && alert.published_ts * 1000 > sinceMs);
  if (news.length > 0) {
    const injuries = news.filter((alert) => alert.event_type === "injury/status").length;
    items.push({
      key: "news",
      label: "Your players",
      value: injuries > 0 ? `${plural(news.length, "update", "updates")}, ${injuries} injury/status` : plural(news.length, "update", "updates"),
      segment: "alerts",
    });
  }
  return items;
}
