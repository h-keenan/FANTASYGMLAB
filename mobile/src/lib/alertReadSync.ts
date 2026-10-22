/**
 * Cross-device Alerts read state (mirrors web-next/src/lib/alertReadSync.ts).
 *
 * The server (POST /v1/leagues/{id}/alerts/read -> Supabase
 * `mobile_alert_reads`) is the source of truth, and the web app reads and
 * writes the same table, so an alert read on the website comes back as
 * `read: true` here and vice versa. This module only covers the gap between
 * "tapped" and "the server has it": a tap marks the row read immediately and
 * is remembered as *pending* until the POST answers `ok: true`. A pending
 * read survives the app being killed, a dropped connection, or a backend
 * answer of `ok: false`, and is retried the next time Alerts loads. Once the
 * server reports the alert read, the pending entry is dropped.
 *
 * Pure and RN-free on purpose: storage (AsyncStorage in the app) and the
 * POST are injected, so this runs under plain Node's test runner. Every
 * storage failure degrades to plain server-only behavior.
 */

export interface AlertReadStorage {
  getItem(key: string): Promise<string | null>;
  setItem(key: string, value: string): Promise<void>;
}

export type PostAlertRead = (leagueId: string, alertKey: string) => Promise<{ ok: boolean } | null | undefined>;

interface ReadableAlert {
  alert_key: string;
  read: boolean;
}

type PendingStore = Record<string, Record<string, number>>;

export const ALERT_READS_PENDING_STORAGE_KEY = 'fgl:alert-reads-pending:v1';
const MAX_PENDING_PER_SCOPE = 200;
const MAX_PENDING_AGE_MS = 30 * 24 * 60 * 60 * 1000;

function scopeKey(userId: string, leagueId: string): string {
  return `${userId || 'anon'}:${leagueId}`;
}

function prune(entries: Record<string, number>, now: number): Record<string, number> {
  const fresh = Object.entries(entries).filter(
    ([key, markedAt]) => key && typeof markedAt === 'number' && now - markedAt < MAX_PENDING_AGE_MS,
  );
  fresh.sort((a, b) => b[1] - a[1]);
  return Object.fromEntries(fresh.slice(0, MAX_PENDING_PER_SCOPE));
}

export function createAlertReadSync(storage: AlertReadStorage, post: PostAlertRead) {
  // Serializes read-modify-write cycles so two quick taps can't overwrite
  // each other's pending entry.
  let queue: Promise<unknown> = Promise.resolve();

  async function readStore(): Promise<PendingStore> {
    try {
      const raw = await storage.getItem(ALERT_READS_PENDING_STORAGE_KEY);
      if (!raw) return {};
      const parsed: unknown = JSON.parse(raw);
      return parsed && typeof parsed === 'object' ? (parsed as PendingStore) : {};
    } catch {
      return {};
    }
  }

  function updateScope(
    userId: string,
    leagueId: string,
    mutate: (entries: Record<string, number>) => Record<string, number>,
  ): Promise<void> {
    const run = queue.then(async () => {
      const store = await readStore();
      const scope = scopeKey(userId, leagueId);
      const next = prune(mutate({ ...(store[scope] ?? {}) }), Date.now());
      if (Object.keys(next).length === 0) delete store[scope];
      else store[scope] = next;
      try {
        await storage.setItem(ALERT_READS_PENDING_STORAGE_KEY, JSON.stringify(store));
      } catch {
        // Storage unavailable: the in-memory optimistic state still applies.
      }
    });
    queue = run.catch(() => undefined);
    return run;
  }

  async function pendingKeys(userId: string, leagueId: string): Promise<Set<string>> {
    await queue;
    const entries = (await readStore())[scopeKey(userId, leagueId)] ?? {};
    return new Set(Object.keys(prune(entries, Date.now())));
  }

  async function clearPending(userId: string, leagueId: string, alertKeys: string[]): Promise<void> {
    if (alertKeys.length === 0) return;
    await updateScope(userId, leagueId, (entries) => {
      for (const key of alertKeys) delete entries[key];
      return entries;
    });
  }

  async function pushRead(userId: string, leagueId: string, alertKey: string): Promise<boolean> {
    try {
      const result = await post(leagueId, alertKey);
      if (result?.ok) {
        await clearPending(userId, leagueId, [alertKey]);
        return true;
      }
    } catch {
      // Offline / transient: stays pending, retried on the next load.
    }
    return false;
  }

  function overlay<T extends ReadableAlert>(items: T[], pending: Set<string>): T[] {
    if (pending.size === 0) return items;
    return items.map((item) => (pending.has(item.alert_key) && !item.read ? { ...item, read: true } : item));
  }

  return {
    pendingKeys,

    /** Mark one alert read: remembered locally first, then synced. */
    async markRead(userId: string, leagueId: string, alertKey: string): Promise<boolean> {
      await updateScope(userId, leagueId, (entries) => ({ ...entries, [alertKey]: Date.now() }));
      return pushRead(userId, leagueId, alertKey);
    },

    /** Read-only: render pending reads as read (for counts/badges). */
    async overlayPending<T extends ReadableAlert>(userId: string, leagueId: string, items: T[]): Promise<T[]> {
      return overlay(items, await pendingKeys(userId, leagueId));
    },

    /**
     * Merge a fresh server response with pending reads: rows the server
     * already reports read leave the pending set, the remaining pending rows
     * render as read and are re-sent in the background.
     */
    async reconcile<T extends ReadableAlert>(userId: string, leagueId: string, items: T[]): Promise<T[]> {
      const pending = await pendingKeys(userId, leagueId);
      if (pending.size === 0) return items;
      const visible = new Set(items.map((item) => item.alert_key));
      const confirmed = items.filter((item) => item.read && pending.has(item.alert_key)).map((item) => item.alert_key);
      await clearPending(userId, leagueId, confirmed);
      for (const key of pending) {
        if (visible.has(key) && !confirmed.includes(key)) void pushRead(userId, leagueId, key);
      }
      return overlay(items, pending);
    },
  };
}

export type AlertReadSync = ReturnType<typeof createAlertReadSync>;
