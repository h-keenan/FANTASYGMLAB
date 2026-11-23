/**
 * Account isolation core, one definition for web and app (byte-identical lib twin, imports nothing).
 * Audit: docs/audits/2026-11-account-isolation.md.
 *
 * Scenario: user A signs out, user B signs in on the same browser or phone. B must never see A's leagues, games,
 * notes, seen-state or cached responses. Three rules make that structural instead of per-screen:
 *
 *  1. Per-user local state is stored under `u:<userId>:<baseKey>` (`userScopedKey`). A second account reads a different key.
 *  2. Keys that cannot carry a user (read by an inline script before React, or written before sign-in on purpose) are
 *     listed in PURGE_UNSCOPED_* and cleared on sign-out and on user change.
 *  3. One purge per platform (`web: lib/userStorage.ts purgeAccountStorage`, `app: lib/userStorage.ts purgeAccountStorage`)
 *     removes every key `isAccountPurgeKey` names, plus the in-memory and React Query caches.
 *
 * Keys that hold only a device preference (theme, density, age gate, ...) stay global and are listed in
 * DEVICE_LEVEL_KEYS with the reason. Supabase's own auth storage is never touched: nothing here matches its keys.
 *
 * Kill switch: ACCOUNT_ISOLATION_ENABLED. `false` restores the previous behaviour exactly (plain keys, no migration,
 * purge removes nothing).
 */
export const ACCOUNT_ISOLATION_ENABLED = true;

export const USER_SCOPE_PREFIX = "u:";

/** `u:<userId>:<baseKey>`, or null when nobody is signed in (callers then read nothing and write nothing). Disabled: the plain key. */
export function userScopedKey(
  userId: string | null | undefined,
  baseKey: string,
  enabled: boolean = ACCOUNT_ISOLATION_ENABLED,
): string | null {
  if (!enabled) return baseKey;
  if (!userId) return null;
  return `${USER_SCOPE_PREFIX}${userId}:${baseKey}`;
}

export function isUserScopedKey(key: string): boolean {
  return key.startsWith(USER_SCOPE_PREFIX);
}

/**
 * Plain (pre-isolation) keys that now live under the user scope. Entries ending in ":" or "." are prefixes
 * (the league / game / screen id follows). On first sign-in after the upgrade each one found is moved to the
 * signed-in user's scope (read once, written scoped, plain key deleted), so no setting is lost.
 */
export const LEGACY_SCOPED_BASES: readonly string[] = [
  // web
  "fgl:sim-notif-read:",
  "fgl:sim-rookie-notice:",
  "sim.realism.banner.",
  "fgl:compare-recent:",
  "fd:guess-the-player-dismissed-pick-id",
  "fd:guess-the-player-name-match-dismissed-pick-id",
  "fd:trade-outcome-prompt-dismissed",
  // app
  "fgl:compare-recent",
  "fgl:dashboard-seen-recs:",
  "fgl:trade-hub-seen:",
  "fgl:recap-opened:",
  "fgl:last-league",
  "fgl:trial-lapsed-shown-expiration",
  "fgl:guess-the-player-dismissed-pick-id",
  "fgl:guess-the-player-name-match-dismissed-pick-id",
  // app: personal preference (do you follow college football), scoped per user by product decision
  "fgl:college-football-prompt-answered",
  "fgl:college-football-interest",
];

/**
 * User-scoped bases the purge leaves in place: personal preferences the same person should not be asked for
 * again after signing out and back in. They stay under `u:<userId>:<base>`, so another account never reads them.
 */
export const USER_SCOPED_KEEP_BASES: readonly string[] = [
  "fgl:college-football-prompt-answered",
  "fgl:college-football-interest",
];

function isKeptUserScopedKey(key: string): boolean {
  if (!isUserScopedKey(key)) return false;
  const rest = key.slice(USER_SCOPE_PREFIX.length);
  const cut = rest.indexOf(":");
  return cut > 0 && USER_SCOPED_KEEP_BASES.includes(rest.slice(cut + 1));
}

/**
 * Keys that stay unscoped because something reads them without a user (an inline script, or a hand-off written
 * before sign-in). They are cleared on sign-out and on user change. Exact keys, or prefixes ending in ":".
 */
export const PURGE_UNSCOPED_KEYS: readonly string[] = [
  // web: valuation lens detected per league id (read by the inline early-fetch script before React)
  "fgl.detectedLens.v1",
  // web: the league last opened on Today (read by the inline early-fetch script and the landing redirect before auth loads)
  "fgl.lastLeague.v1",
  // web: return paths written before sign-in so the right page opens after it
  "fd_protected_route_return_path",
  "fd_auth_return_path",
  // web: a trade handed from the public analyzer to the signed-in one
  "fd_pending_bridge_trade_v1",
  // web: derived Portfolio snapshots (already user-keyed by their own helper; cleared here as well)
  "fd:portfolio:v1:",
];

/**
 * Already keyed by a user id in their own key shape, hold only progress flags, and are kept across sign-out so a
 * returning user does not repeat onboarding. Listed so the guard and the audit know they are deliberate.
 */
export const USER_KEYED_KEEP_PREFIXES: readonly string[] = [
  "fd:start-here:v1:",
  "fgl:onboarding:",
  "fd:last-visit:v1:",
  "fgl:alert-reads-pending:v1",
];

/** Global on purpose: device preferences, anonymous identifiers, pre-sign-in capture. Each carries why. */
export const DEVICE_LEVEL_KEYS: ReadonlyArray<{ key: string; why: string }> = [
  { key: "fgl:theme-mode", why: "Appearance of this device; no account data." },
  { key: "fgl:ui-density", why: "Appearance of this device; no account data." },
  { key: "fgl:effects-prefs:v1", why: "Motion and effects choice for this device." },
  { key: "fgl:orb-horizontal-fraction", why: "Where the orb sits on this screen." },
  { key: "fgl:player-list-view-mode:", why: "List or grid layout per screen; no account data." },
  { key: "fgl:sim-to-prefs", why: "Sim-to control layout; no account data." },
  { key: "fd.sim.celebrations", why: "Celebration animation toggle; no account data." },
  { key: "fgl:sim-open:", why: "Whether a section is expanded, per section id; no account data." },
  { key: "fgl:nav", why: "Shell navigation style of this browser." },
  { key: "fgl:age-gate-passed", why: "The person at this device passed the age gate; legal gate, not an account fact." },
  { key: "fd-help-seen:orb-menu", why: "Hint about the orb control itself; same device, same control." },
  { key: "fgl:push-prompt-dismissed-at", why: "The OS permission prompt belongs to the device, not the account." },
  { key: "fgl:onboarding-complete", why: "Per-install first-run gate (the intro tutorial), device-level by product decision (2026-11): the intro is about this install, so a second account on the phone does not repeat it." },
  { key: "fgl:trial-offer-pending", why: "Arms the first-value offer after this install's first onboarding; the offer itself re-checks the account's plan on the server." },
  { key: "fgl:experience-level", why: "Device display choice (beginner or advanced copy)." },
  { key: "fgl:showcase-mode", why: "Screenshot/demo display mode of this device." },
  { key: "fd_privacy_mode", why: "Privacy masking is a viewing choice of this device and must stay on across accounts." },
  { key: "fd_privacy_labels", why: "Session-only masking labels; hashes, no real names." },
  { key: "dynastygm_analytics_anon_id", why: "Anonymous device id minted before sign-in." },
  { key: "dynastygm_analytics_queue_v1", why: "Anonymous analytics queue; events carry no account content." },
  { key: "fd_attribution_v1", why: "First-touch attribution is captured before sign-in; consumed server-side, no account data." },
  { key: "fd_pending_ref", why: "Referral code captured before sign-in; cleared when consumed." },
  { key: "fgl:pending-referral-code", why: "Referral code captured before sign-in; cleared when consumed." },
  { key: "fgl:last-storage-user", why: "Marker of which user this browser's scoped state belongs to; lets a user change purge the previous one." },
  { key: "fgl:auth-scope-user-id", why: "The marker that says which user the app caches belong to; the purge reads it." },
  { key: "fgl:react-query-cache", why: "Persisted React Query blob; user-rooted keys, cleared by the purge." },
];

/** True when `key` is something the account purge must remove. */
export function isAccountPurgeKey(key: string): boolean {
  if (isUserScopedKey(key)) return !isKeptUserScopedKey(key);
  for (const k of PURGE_UNSCOPED_KEYS) {
    if (key === k || (k.endsWith(":") && key.startsWith(k))) return true;
  }
  for (const base of LEGACY_SCOPED_BASES) {
    if (key === base || ((base.endsWith(":") || base.endsWith(".")) && key.startsWith(base))) return true;
  }
  return false;
}

/** The subset of `allKeys` to remove; empty when the kill switch is off. */
export function planPurge(allKeys: readonly string[], enabled: boolean = ACCOUNT_ISOLATION_ENABLED): string[] {
  if (!enabled) return [];
  return allKeys.filter(isAccountPurgeKey);
}

/** The legacy plain keys in `allKeys` that should move into a user's scope. */
export function planMigration(allKeys: readonly string[], enabled: boolean = ACCOUNT_ISOLATION_ENABLED): string[] {
  if (!enabled) return [];
  return allKeys.filter((key) => {
    if (isUserScopedKey(key)) return false;
    return LEGACY_SCOPED_BASES.some((base) => key === base || ((base.endsWith(":") || base.endsWith(".")) && key.startsWith(base)));
  });
}

export interface SyncKeyValueStore {
  readonly length: number;
  key(index: number): string | null;
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
}

export interface AsyncKeyValueStore {
  getAllKeys(): Promise<readonly string[]>;
  getItem(key: string): Promise<string | null>;
  setItem(key: string, value: string): Promise<unknown>;
  removeItem(key: string): Promise<unknown>;
  multiRemove?(keys: string[]): Promise<unknown>;
}

function syncKeys(store: SyncKeyValueStore): string[] {
  const keys: string[] = [];
  for (let i = 0; i < store.length; i += 1) {
    const key = store.key(i);
    if (key) keys.push(key);
  }
  return keys;
}

/**
 * Moves every legacy plain key into `userId`'s scope: read once, write scoped (unless the user already has a
 * scoped value, which wins), delete the plain key. Never throws; returns the number of keys moved.
 */
export function migrateLegacyKeysSync(store: SyncKeyValueStore, userId: string, enabled: boolean = ACCOUNT_ISOLATION_ENABLED): number {
  let moved = 0;
  try {
    for (const key of planMigration(syncKeys(store), enabled)) {
      try {
        const scoped = userScopedKey(userId, key, enabled);
        const value = store.getItem(key);
        if (scoped && value !== null && store.getItem(scoped) === null) store.setItem(scoped, value);
        store.removeItem(key);
        moved += 1;
      } catch {
        /* leave this key where it is; the next sign-in retries */
      }
    }
  } catch {
    /* storage unavailable */
  }
  return moved;
}

export async function migrateLegacyKeysAsync(
  store: AsyncKeyValueStore,
  userId: string,
  enabled: boolean = ACCOUNT_ISOLATION_ENABLED,
): Promise<number> {
  let moved = 0;
  try {
    for (const key of planMigration(await store.getAllKeys(), enabled)) {
      try {
        const scoped = userScopedKey(userId, key, enabled);
        const value = await store.getItem(key);
        if (scoped && value !== null && (await store.getItem(scoped)) === null) await store.setItem(scoped, value);
        await store.removeItem(key);
        moved += 1;
      } catch {
        /* leave this key where it is; the next sign-in retries */
      }
    }
  } catch {
    /* storage unavailable */
  }
  return moved;
}

/** Removes every purge key from a sync store (web localStorage or sessionStorage). Returns the count removed. */
export function purgeSyncStore(store: SyncKeyValueStore, enabled: boolean = ACCOUNT_ISOLATION_ENABLED): number {
  let removed = 0;
  try {
    for (const key of planPurge(syncKeys(store), enabled)) {
      try {
        store.removeItem(key);
        removed += 1;
      } catch {
        /* ignore */
      }
    }
  } catch {
    /* storage unavailable */
  }
  return removed;
}

export async function purgeAsyncStore(store: AsyncKeyValueStore, enabled: boolean = ACCOUNT_ISOLATION_ENABLED): Promise<number> {
  try {
    const keys = planPurge(await store.getAllKeys(), enabled);
    if (keys.length === 0) return 0;
    if (store.multiRemove) await store.multiRemove(keys);
    else for (const key of keys) await store.removeItem(key);
    return keys.length;
  } catch {
    return 0;
  }
}
