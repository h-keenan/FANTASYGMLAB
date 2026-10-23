import { beforeEach, describe, expect, it } from "vitest";

import {
  PRIVACY_STORAGE_KEY,
  createMasker,
  isPrivacyMode,
  maskIfPrivate,
  maskSavedLeagueRows,
  resetPrivacyForTests,
  setPrivacyMode,
  unmaskOutgoing,
} from "./privacy";

const SAMPLE = {
  league_name: "Revivalary Dynasty",
  user: { email: "zach@real.com", sleeper_username: "zachgm" },
  teams: [
    { roster_id: 1, team_name: "Gridiron Gang", owner_name: "Zach Real", owner_handle: "zachgm", avatar_url: "https://sleepercdn.com/avatars/abc" },
    { roster_id: 2, team_name: "Pat Mahomies", owner_name: "Pat Smith", owner_handle: "psmith", avatar_url: null },
  ],
  players: [{ player_id: "4046", name: "Patrick Mahomes", position: "QB", team: "KC", opponent: "BUF" }],
  alert: { message: "Pat Mahomies offered a trade for Patrick Mahomes", title: "Gridiron Gang is rising" },
};

beforeEach(() => {
  resetPrivacyForTests();
  window.localStorage.clear();
  window.sessionStorage.clear();
});

describe("createMasker", () => {
  it("replaces names, handles, league names, email and avatars with generic labels", () => {
    const out = createMasker().mask(SAMPLE);
    expect(out.league_name).toBe("Sample League");
    expect(out.user.email).toBe("hidden@example.com");
    expect(out.user.sleeper_username).toBe("manager_1");
    expect(out.teams[0]).toMatchObject({ team_name: "Team A", owner_name: "Manager 1", avatar_url: null });
    expect(out.teams[1]).toMatchObject({ team_name: "Team B", owner_name: "Manager 2" });
    expect(JSON.stringify(out)).not.toMatch(/Gridiron|Revivalary|zach|Smith|sleepercdn/i);
  });

  it("keeps real NFL player names, positions and NFL teams", () => {
    const out = createMasker().mask(SAMPLE);
    expect(out.players[0]).toEqual(SAMPLE.players[0]);
  });

  it("scrubs known names inside free text but not player names", () => {
    const out = createMasker().mask(SAMPLE);
    expect(out.alert.message).toBe("Team B offered a trade for Patrick Mahomes");
    expect(out.alert.title).toBe("Team A is rising");
  });

  it("is deterministic per id and idempotent", () => {
    const m = createMasker();
    const once = m.mask(SAMPLE);
    expect(m.mask(SAMPLE)).toEqual(once);
    expect(m.mask(once)).toEqual(once);
    expect(m.label("team", "Gridiron Gang")).toBe("Team A");
  });

  it("keeps labels stable across reloads in one session (sessionStorage counters)", () => {
    createMasker(window.sessionStorage).mask(SAMPLE);
    const b = createMasker(window.sessionStorage);
    expect(b.label("team", "Pat Mahomies")).toBe("Team B");
    expect(b.label("league", "Revivalary Dynasty")).toBe("Sample League");
    expect(window.sessionStorage.getItem("fd_privacy_labels") || "").not.toMatch(/Gridiron/);
  });

  it("names a second league Sample Dynasty League", () => {
    const m = createMasker();
    expect(m.label("league", "A")).toBe("Sample League");
    expect(m.label("league", "B")).toBe("Sample Dynasty League");
    expect(m.label("league", "C")).toBe("Sample League 3");
  });

  it("maps masked labels back to real values for outgoing bodies", () => {
    const m = createMasker();
    m.mask(SAMPLE);
    expect(m.unmask({ league_name: "Sample League", other: "x", ids: ["Team A"] })).toEqual({
      league_name: "Revivalary Dynasty",
      other: "x",
      ids: ["Gridiron Gang"],
    });
  });

  it("masks league `name` only on league objects, not players", () => {
    const out = createMasker().mask({ leagues: [{ league_id: "9", name: "My League" }], p: { player_id: "1", name: "Josh Allen" } });
    expect(out.leagues[0].name).toBe("Sample League");
    expect(out.p.name).toBe("Josh Allen");
  });
});

describe("privacy toggle", () => {
  it("is off by default and persists in localStorage", () => {
    expect(isPrivacyMode()).toBe(false);
    setPrivacyMode(true);
    expect(window.localStorage.getItem(PRIVACY_STORAGE_KEY)).toBe("1");
    resetPrivacyForTests();
    expect(isPrivacyMode()).toBe(true);
    setPrivacyMode(false);
    expect(window.localStorage.getItem(PRIVACY_STORAGE_KEY)).toBeNull();
  });

  it("only transforms while on", () => {
    expect(maskIfPrivate(SAMPLE)).toBe(SAMPLE);
    setPrivacyMode(true);
    expect(maskIfPrivate(SAMPLE).league_name).toBe("Sample League");
    expect(unmaskOutgoing({ league_name: "Sample League" }).league_name).toBe("Revivalary Dynasty");
    expect(maskSavedLeagueRows([{ league_id: "1", league_name: "Revivalary Dynasty" }])[0].league_name).toBe("Sample League");
  });
});
