import { beforeEach, describe, expect, it } from "vitest";

import {
  DEVICE_LEVEL_KEYS,
  isAccountPurgeKey,
  migrateLegacyKeysSync,
  planMigration,
  planPurge,
  purgeSyncStore,
  userScopedKey,
} from "./accountScope";
import { coalesceRead } from "./requestCache";
import { applySessionUser, purgeAccountStorage, resetUserStorageForTests, userGet, userSet } from "./userStorage";

const SUPABASE_KEY = "sb-abc-auth-token";

beforeEach(() => {
  window.localStorage.clear();
  window.sessionStorage.clear();
  resetUserStorageForTests();
});

describe("account isolation on one browser", () => {
  it("B never sees A's state after A signs out and B signs in", () => {
    applySessionUser("A");
    userSet("fgl:compare-recent:L1", '["p1"]');
    userSet("fd:trade-outcome-prompt-dismissed", "1", "session");
    window.localStorage.setItem("fgl.detectedLens.v1", '{"L1":"Dynasty"}');
    window.localStorage.setItem(SUPABASE_KEY, "tokens");
    expect(userGet("fgl:compare-recent:L1")).toBe('["p1"]');

    applySessionUser(null);
    applySessionUser("B");
    expect(userGet("fgl:compare-recent:L1")).toBeNull();
    expect(userGet("fd:trade-outcome-prompt-dismissed", "session")).toBeNull();
    for (let i = 0; i < window.localStorage.length; i += 1) {
      const key = window.localStorage.key(i) ?? "";
      expect(key.startsWith("u:A:")).toBe(false);
    }
    expect(window.localStorage.getItem("fgl.detectedLens.v1")).toBeNull();
    // Supabase's own auth storage is never touched by the purge.
    expect(window.localStorage.getItem(SUPABASE_KEY)).toBe("tokens");
  });

  it("a direct switch A to B without a sign-out event still purges A", () => {
    applySessionUser("A");
    userSet("fd:guess-the-player-dismissed-pick-id", "pick-1");
    window.localStorage.setItem("fd_auth_return_path", '{"path":"/dashboard/L1","at":1}');
    applySessionUser("B");
    expect(userGet("fd:guess-the-player-dismissed-pick-id")).toBeNull();
    expect(window.localStorage.getItem("fd_auth_return_path")).toBeNull();
  });

  it("a reload into another account (marker from A, first session is B) purges A's unscoped leftovers", () => {
    applySessionUser("A");
    window.localStorage.setItem("fd_pending_bridge_trade_v1", "{}");
    resetUserStorageForTests(); // process restart
    applySessionUser("B");
    expect(window.localStorage.getItem("fd_pending_bridge_trade_v1")).toBeNull();
  });

  it("the same user reloading keeps their state; a token refresh does not purge", () => {
    applySessionUser("A");
    userSet("fgl:compare-recent:L1", '["p1"]');
    applySessionUser("A");
    resetUserStorageForTests();
    applySessionUser("A");
    expect(userGet("fgl:compare-recent:L1")).toBe('["p1"]');
  });

  it("an initial signed-out load keeps the pre-sign-in hand-off keys", () => {
    window.localStorage.setItem("fd_protected_route_return_path", '{"path":"/pricing","at":1}');
    applySessionUser(null);
    expect(window.localStorage.getItem("fd_protected_route_return_path")).not.toBeNull();
  });

  it("nobody signed in: reads are null and writes are dropped", () => {
    userSet("fgl:compare-recent:L1", '["p1"]');
    expect(userGet("fgl:compare-recent:L1")).toBeNull();
    expect(window.localStorage.length).toBe(0);
  });

  it("the purge keeps every device-level key and clears the read cache", async () => {
    applySessionUser("A");
    for (const { key } of DEVICE_LEVEL_KEYS) if (!key.endsWith(":")) window.localStorage.setItem(key, "x");
    let loads = 0;
    const load = async () => ++loads;
    await coalesceRead("tok|-|/v1/x", true, load);
    await coalesceRead("tok|-|/v1/x", true, load);
    expect(loads).toBe(1);
    purgeAccountStorage();
    await coalesceRead("tok|-|/v1/x", true, load);
    expect(loads).toBe(2);
    for (const { key } of DEVICE_LEVEL_KEYS) if (!key.endsWith(":")) expect(window.localStorage.getItem(key)).toBe("x");
  });
});

describe("migration of pre-isolation keys", () => {
  const legacy: Record<string, string> = {
    "fgl:sim-notif-read:g1": "12",
    "fgl:sim-rookie-notice:g1": "1",
    "sim.realism.banner.g1.2.a": "1",
    "fgl:compare-recent:L1": '["p9"]',
    "fd:guess-the-player-dismissed-pick-id": "pick-7",
    "fd:guess-the-player-name-match-dismissed-pick-id": "pair-7",
  };

  it("the first user to sign in after the upgrade keeps every setting; the plain keys are gone; a second user gets none", () => {
    for (const [k, v] of Object.entries(legacy)) window.localStorage.setItem(k, v);
    window.localStorage.setItem("fgl:theme-mode", "dark");
    applySessionUser("A");
    for (const [k, v] of Object.entries(legacy)) {
      expect(userGet(k)).toBe(v);
      expect(window.localStorage.getItem(k)).toBeNull();
    }
    expect(window.localStorage.getItem("fgl:theme-mode")).toBe("dark");

    applySessionUser("B");
    for (const k of Object.keys(legacy)) expect(userGet(k)).toBeNull();
  });

  it("migrating twice is a no-op and an already scoped value wins", () => {
    const store = window.localStorage;
    store.setItem("fgl:compare-recent:L1", "old");
    store.setItem("u:A:fgl:compare-recent:L1", "new");
    expect(migrateLegacyKeysSync(store, "A")).toBe(1);
    expect(store.getItem("u:A:fgl:compare-recent:L1")).toBe("new");
    expect(store.getItem("fgl:compare-recent:L1")).toBeNull();
    expect(migrateLegacyKeysSync(store, "A")).toBe(0);
  });
});

describe("kill switch", () => {
  it("disabled: plain keys, no migration, no purge", () => {
    window.localStorage.setItem("fgl:compare-recent:L1", "x");
    window.localStorage.setItem("u:A:foo", "y");
    expect(userScopedKey("A", "fgl:compare-recent:L1", false)).toBe("fgl:compare-recent:L1");
    expect(migrateLegacyKeysSync(window.localStorage, "A", false)).toBe(0);
    expect(purgeSyncStore(window.localStorage, false)).toBe(0);
    expect(planPurge(["u:A:foo"], false)).toEqual([]);
    expect(planMigration(["fgl:compare-recent:L1"], false)).toEqual([]);
  });
});

describe("registry", () => {
  it("no device-level key is also a purge key", () => {
    for (const { key } of DEVICE_LEVEL_KEYS) expect(isAccountPurgeKey(key)).toBe(false);
  });
});
