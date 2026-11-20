/**
 * App side of account isolation, storage-agnostic so `node --test` can run it with an in-memory store
 * (see accountScope.ts and docs/audits/2026-11-account-isolation.md). `userStorage.ts` binds AsyncStorage.
 *
 * Per-user state lives under `u:<userId>:<baseKey>`. With nobody signed in, reads return null and writes are dropped.
 * AuthContext calls `applyUser` on every session resolution and `purge` on sign-out, delete-account and user change.
 */
import {
  ACCOUNT_ISOLATION_ENABLED,
  migrateLegacyKeysAsync,
  purgeAsyncStore,
  userScopedKey,
  type AsyncKeyValueStore,
} from './accountScope.ts';

export interface UserStorage {
  get(baseKey: string): Promise<string | null>;
  set(baseKey: string, value: string): Promise<void>;
  remove(baseKey: string): Promise<void>;
  /** Removes every user-scoped and unscoped account key. Local only; never throws. */
  purge(): Promise<void>;
  /** Records the signed-in user (null = signed out) and moves pre-isolation keys into that user's scope. */
  applyUser(userId: string | null): Promise<void>;
  currentUserId(): string | null;
}

export function createUserStorage(store: AsyncKeyValueStore, enabled: boolean = ACCOUNT_ISOLATION_ENABLED): UserStorage {
  let userId: string | null = null;
  let ready: Promise<unknown> = Promise.resolve();

  return {
    async get(baseKey) {
      const key = userScopedKey(userId, baseKey, enabled);
      if (!key) return null;
      try {
        await ready;
        return (await store.getItem(key)) ?? null;
      } catch {
        return null;
      }
    },
    async set(baseKey, value) {
      const key = userScopedKey(userId, baseKey, enabled);
      if (!key) return;
      try {
        await ready;
        await store.setItem(key, value);
      } catch {
        /* best effort */
      }
    },
    async remove(baseKey) {
      const key = userScopedKey(userId, baseKey, enabled);
      if (!key) return;
      try {
        await ready;
        await store.removeItem(key);
      } catch {
        /* best effort */
      }
    },
    async purge() {
      await purgeAsyncStore(store, enabled);
    },
    async applyUser(next) {
      userId = next;
      if (next && enabled) {
        ready = migrateLegacyKeysAsync(store, next, enabled);
        await ready;
      }
    },
    currentUserId() {
      return userId;
    },
  };
}
