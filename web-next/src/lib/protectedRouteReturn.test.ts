import { describe, expect, it } from "vitest";

import {
  clearProtectedReturnPath,
  readProtectedReturnPath,
  safeProtectedPath,
  storeProtectedReturnPath,
} from "./protectedRouteReturn";

function memStorage() {
  const m = new Map<string, string>();
  return {
    getItem: (k: string) => m.get(k) ?? null,
    setItem: (k: string, v: string) => void m.set(k, v),
    removeItem: (k: string) => void m.delete(k),
  };
}

describe("safeProtectedPath", () => {
  it("accepts same-origin relative paths", () => {
    expect(safeProtectedPath("/premium")).toBe("/premium");
    expect(safeProtectedPath("/connect-league?x=1#y")).toBe("/connect-league?x=1#y");
  });

  it.each(["https://evil.com", "//evil.com", "/\\evil.com", "javascript:alert(1)", "premium", "", "/a\nb"])(
    "rejects %j",
    (v) => expect(safeProtectedPath(v)).toBeNull(),
  );

  it("rejects non-strings", () => {
    expect(safeProtectedPath(null)).toBeNull();
    expect(safeProtectedPath(undefined)).toBeNull();
  });
});

describe("store/read/clearProtectedReturnPath", () => {
  it("round-trips a stored path", () => {
    const storage = memStorage();
    storeProtectedReturnPath(storage, "/premium");
    expect(readProtectedReturnPath(storage)).toBe("/premium");
  });

  it("never stores an unsafe path", () => {
    const storage = memStorage();
    storeProtectedReturnPath(storage, "https://evil.com");
    expect(readProtectedReturnPath(storage)).toBeNull();
  });

  it("expires after the TTL", () => {
    const storage = memStorage();
    const at = 1_000_000;
    storeProtectedReturnPath(storage, "/connect-league", at);
    expect(readProtectedReturnPath(storage, at + 59 * 60 * 1000)).toBe("/connect-league");
    expect(readProtectedReturnPath(storage, at + 61 * 60 * 1000)).toBeNull();
  });

  it("rejects a clock-skewed future timestamp", () => {
    const storage = memStorage();
    storeProtectedReturnPath(storage, "/premium", 1_000_000);
    expect(readProtectedReturnPath(storage, 999_000)).toBeNull();
  });

  it("clear removes it", () => {
    const storage = memStorage();
    storeProtectedReturnPath(storage, "/premium");
    clearProtectedReturnPath(storage);
    expect(readProtectedReturnPath(storage)).toBeNull();
  });

  it("is a no-op without storage", () => {
    expect(() => storeProtectedReturnPath(null, "/premium")).not.toThrow();
    expect(readProtectedReturnPath(null)).toBeNull();
    expect(() => clearProtectedReturnPath(undefined)).not.toThrow();
  });

  it("tolerates malformed JSON already in storage", () => {
    const storage = memStorage();
    storage.setItem("fd_protected_route_return_path", "{not json");
    expect(readProtectedReturnPath(storage)).toBeNull();
  });
});
