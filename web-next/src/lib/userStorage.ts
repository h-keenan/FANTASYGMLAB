/**
 * Web side of account isolation (see accountScope.ts and docs/audits/2026-11-account-isolation.md).
 *
 * AuthContext is the single writer: `applySessionUser` is called with the session's user id on every session
 * resolution. Screens read and write per-user state through `userGet` / `userSet` / `userRemove`, which store under
 * `u:<userId>:<baseKey>`. With nobody signed in they read null and write nothing.
 */
import { ACCOUNT_ISOLATION_ENABLED, migrateLegacyKeysSync, purgeSyncStore, userScopedKey } from "./accountScope";
import { resetAccountCaches } from "./accountCaches";
import { clearRequestCache } from "./requestCache";

const LAST_USER_MARKER_KEY = "fgl:last-storage-user";

export type StorageKind = "local" | "session";

let currentUserId: string | null = null;

function store(kind: StorageKind): Storage | null {
  try {
    if (typeof window === "undefined") return null;
    return kind === "local" ? window.localStorage : window.sessionStorage;
  } catch {
    return null;
  }
}

export function getStorageUserId(): string | null {
  return currentUserId;
}

export function userGet(baseKey: string, kind: StorageKind = "local"): string | null {
  const key = userScopedKey(currentUserId, baseKey);
  if (!key) return null;
  try {
    return store(kind)?.getItem(key) ?? null;
  } catch {
    return null;
  }
}

export function userSet(baseKey: string, value: string, kind: StorageKind = "local"): void {
  const key = userScopedKey(currentUserId, baseKey);
  if (!key) return;
  try {
    store(kind)?.setItem(key, value);
  } catch {
    /* storage unavailable: the in-memory state still applies */
  }
}

export function userRemove(baseKey: string, kind: StorageKind = "local"): void {
  const key = userScopedKey(currentUserId, baseKey);
  if (!key) return;
  try {
    store(kind)?.removeItem(key);
  } catch {
    /* ignore */
  }
}

/** The one web purge: every user-scoped and unscoped account key in local and session storage, plus the read cache. Local only. */
export function purgeAccountStorage(): void {
  if (!ACCOUNT_ISOLATION_ENABLED) return;
  for (const kind of ["local", "session"] as const) {
    const s = store(kind);
    if (s) purgeSyncStore(s);
  }
  clearRequestCache();
  resetAccountCaches();
}

/**
 * Tells storage which user the session belongs to. A user to nobody transition purges; a different user than the
 * one this browser last held purges (covers a reload into another account); the first sign-in after the upgrade
 * moves the old plain keys into that user's scope.
 */
export function applySessionUser(userId: string | null): void {
  if (!ACCOUNT_ISOLATION_ENABLED) {
    currentUserId = userId;
    return;
  }
  const previous = currentUserId;
  if (!userId) {
    currentUserId = null;
    if (previous) purgeAccountStorage();
    return;
  }
  if (previous === userId) return;
  const local = store("local");
  let marker: string | null = null;
  try {
    marker = local?.getItem(LAST_USER_MARKER_KEY) ?? null;
  } catch {
    marker = null;
  }
  if ((previous && previous !== userId) || (marker && marker !== userId)) purgeAccountStorage();
  currentUserId = userId;
  try {
    local?.setItem(LAST_USER_MARKER_KEY, userId);
  } catch {
    /* ignore */
  }
  if (!marker || marker === userId) {
    // Plain keys from before isolation belong to the first account that signs in after the upgrade.
    for (const kind of ["local", "session"] as const) {
      const s = store(kind);
      if (s) migrateLegacyKeysSync(s, userId);
    }
  }
}

/** Test helper. */
export function resetUserStorageForTests(): void {
  currentUserId = null;
}
