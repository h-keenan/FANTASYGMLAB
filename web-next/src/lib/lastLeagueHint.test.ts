import { beforeEach, describe, expect, it } from "vitest";

import { clearLastLeague, hasPendingLandingOverride, LAST_LEAGUE_STORAGE_KEY, readLastLeague, writeLastLeague } from "./lastLeagueHint";

beforeEach(() => window.localStorage.clear());

describe("last league hint", () => {
  it("round-trips for the same user only", () => {
    writeLastLeague("u1", "L1", "My League");
    expect(readLastLeague("u1")).toEqual({ uid: "u1", id: "L1", name: "My League" });
    expect(readLastLeague("u2")).toBeNull();
    expect(readLastLeague(null)).toBeNull();
  });

  it("clears only the league that failed", () => {
    writeLastLeague("u1", "L1", "A");
    clearLastLeague("L2");
    expect(readLastLeague("u1")).not.toBeNull();
    clearLastLeague("L1");
    expect(window.localStorage.getItem(LAST_LEAGUE_STORAGE_KEY)).toBeNull();
  });

  it("ignores malformed storage", () => {
    window.localStorage.setItem(LAST_LEAGUE_STORAGE_KEY, "{nope");
    expect(readLastLeague("u1")).toBeNull();
  });

  it("reports a pending return path as an override", () => {
    expect(hasPendingLandingOverride()).toBe(false);
    window.localStorage.setItem("fd_protected_route_return_path", JSON.stringify({ path: "/premium", at: Date.now() }));
    expect(hasPendingLandingOverride()).toBe(true);
  });
});
