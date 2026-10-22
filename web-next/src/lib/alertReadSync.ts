import { api } from "@/lib/api";

/**
 * Cross-device Alerts read state.
 *
 * The server (POST /v1/leagues/{id}/alerts/read -> Supabase
 * `mobile_alert_reads`) is the source of truth, and it is the same table the
 * mobile app writes to, so a read on the phone comes back as `read: true` in
 * GET .../alerts here and vice versa. This module only covers the gap
 * between "tapped" and "the server has it": a tap marks the row read right
 * away and is remembered locally as *pending* until the POST answers
 * `ok: true`. A pending read survives a reload, a dropped connection, or a
 * backend that answered `ok: false` (e.g. the table briefly unavailable),
 * and is retried the next time Alerts loads. Once the server reports the
 * alert read, the pending entry is dropped.
 *
 * Every storage access is wrapped in try/catch: localStorage can throw or be
 * empty (private windows, blocked site data), and then this degrades to
 * the plain server-only behavior.
 */

const STORAGE_KEY = "fgl:alert-reads-pending:v1";
const MAX_PENDING_PER_SCOPE = 200;
const MAX_PENDING_AGE_MS = 30 * 24 * 60 * 60 * 1000;

type PendingStore = Record<string, Record<string, number>>;

interface ReadableAlert {
  alert_key: string;
  read: boolean;
}

function scopeKey(userId: string, leagueId: string): string {
  return `${userId || "anon"}:${leagueId}`;
}

function readStore(): PendingStore {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return {};
    const parsed: unknown = JSON.parse(raw);
    return parsed && typeof parsed === "object" ? (parsed as PendingStore) : {};
  } catch {
    return {};
  }
}

function writeStore(store: PendingStore): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(store));
  } catch {
    // Storage unavailable: the in-memory optimistic state still applies.
  }
}

function prune(entries: Record<string, number>, now: number): Record<string, number> {
  const fresh = Object.entries(entries).filter(
    ([key, markedAt]) => key && typeof markedAt === "number" && now - markedAt < MAX_PENDING_AGE_MS,
  );
  fresh.sort((a, b) => b[1] - a[1]);
  return Object.fromEntries(fresh.slice(0, MAX_PENDING_PER_SCOPE));
}

function updateScope(
  userId: string,
  leagueId: string,
  mutate: (entries: Record<string, number>) => Record<string, number>,
): void {
  const store = readStore();
  const scope = scopeKey(userId, leagueId);
  const next = prune(mutate({ ...(store[scope] ?? {}) }), Date.now());
  if (Object.keys(next).length === 0) delete store[scope];
  else store[scope] = next;
  writeStore(store);
}

export function pendingAlertReadKeys(userId: string, leagueId: string): Set<string> {
  const entries = readStore()[scopeKey(userId, leagueId)] ?? {};
  return new Set(Object.keys(prune(entries, Date.now())));
}

function addPending(userId: string, leagueId: string, alertKey: string): void {
  updateScope(userId, leagueId, (entries) => ({ ...entries, [alertKey]: Date.now() }));
}

function clearPending(userId: string, leagueId: string, alertKeys: string[]): void {
  if (alertKeys.length === 0) return;
  updateScope(userId, leagueId, (entries) => {
    for (const key of alertKeys) delete entries[key];
    return entries;
  });
}

/** POST one read; true only when the server durably recorded it. */
async function pushRead(userId: string, leagueId: string, alertKey: string): Promise<boolean> {
  try {
    const result = await api.markAlertRead(leagueId, alertKey);
    if (result?.ok) {
      clearPending(userId, leagueId, [alertKey]);
      return true;
    }
  } catch {
    // Offline / transient: stays pending and is retried on the next load.
  }
  return false;
}

/** Mark one alert read: remembered locally first, then synced. */
export function markAlertReadSynced(userId: string, leagueId: string, alertKey: string): Promise<boolean> {
  addPending(userId, leagueId, alertKey);
  return pushRead(userId, leagueId, alertKey);
}

/** Pure (no storage writes, no network): render pending reads as read. */
export function overlayPendingAlertReads<T extends ReadableAlert>(userId: string, leagueId: string, items: T[]): T[] {
  const pending = pendingAlertReadKeys(userId, leagueId);
  if (pending.size === 0) return items;
  return items.map((item) => (pending.has(item.alert_key) && !item.read ? { ...item, read: true } : item));
}

/**
 * Merge a fresh server response with this browser's pending reads: rows the
 * server already reports read drop out of the pending set, the remaining
 * pending rows render as read and are re-sent in the background.
 */
export function reconcileAlertReads<T extends ReadableAlert>(userId: string, leagueId: string, items: T[]): T[] {
  const pending = pendingAlertReadKeys(userId, leagueId);
  if (pending.size === 0) return items;
  const visible = new Set(items.map((item) => item.alert_key));
  const confirmed = items.filter((item) => item.read && pending.has(item.alert_key)).map((item) => item.alert_key);
  clearPending(userId, leagueId, confirmed);
  for (const key of pending) {
    // Only retry rows still in the feed; rows that aged out of it simply
    // expire with MAX_PENDING_AGE_MS.
    if (visible.has(key) && !confirmed.includes(key)) void pushRead(userId, leagueId, key);
  }
  return items.map((item) => (pending.has(item.alert_key) && !item.read ? { ...item, read: true } : item));
}
