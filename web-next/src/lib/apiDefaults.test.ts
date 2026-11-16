import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

import {
  normalizeCollegeProspects,
  normalizeCommissionerIntegrity,
  normalizeCommunityTrades,
  normalizeLeagueRankings,
  normalizeLeagueRosters,
  normalizeLeagueTeamProfiles,
  normalizeMe,
  normalizeSharedCommunityTrades,
} from "./apiDefaults";
import { splitTeams } from "./commissionerIntegrity";

const bodies: [string, unknown][] = [
  ["{}", {}],
  ["null", null],
  ["undefined", undefined],
  ["string", "oops"],
  ["array", []],
  ["wrong types", { trades: null, teams: "x" }],
];

describe("response normalizers: an empty or malformed body becomes safe defaults", () => {
  it.each(bodies)("commissioner integrity from %s", (_n, body) => {
    const r = normalizeCommissionerIntegrity(body);
    expect(r.teams).toEqual([]);
    expect(r.collusion).toEqual([]);
    expect(r.inactive).toEqual([]);
    expect(r.limits).toEqual([]);
    expect(() => splitTeams(r.teams)).not.toThrow();
  });

  it.each(bodies)("prospects from %s", (_n, body) => {
    const r = normalizeCollegeProspects(body);
    expect(r.prospects).toEqual([]);
    expect(r.catalog_available).toBe(false);
    expect(r.reason).toBe("");
  });

  it.each(bodies)("community trades from %s", (_n, body) => {
    const r = normalizeCommunityTrades(body);
    expect(r.trades).toEqual([]);
    expect(r.reaction_emoji).toEqual([]);
    expect(normalizeSharedCommunityTrades(body).trades).toEqual([]);
  });

  it.each(bodies)("rosters, profiles, rankings from %s", (_n, body) => {
    expect(normalizeLeagueRosters(body).rosters).toEqual([]);
    expect(normalizeLeagueTeamProfiles(body).profiles).toEqual({});
    expect(normalizeLeagueRankings(body).players).toEqual([]);
  });

  it("me without a user is a Free account with a fail-closed profile", () => {
    const r = normalizeMe({});
    expect(r.user.entitlement).toBe("free");
    expect(r.user.profile_status).toBe("error");
    expect(r.user.email).toBe("");
    expect(r.premium_benefits).toEqual([]);
  });
});

describe("response normalizers keep real data untouched", () => {
  it("passes a full prospects payload through", () => {
    const prospect = { id: "p1", name: "A", position: "QB", school: "S", draft_year: 2027, aggregate: { avg_grade: 80, scout_count: 3, avg_round_projection: 1.2 }, my_report: null, on_watchlist: true };
    const r = normalizeCollegeProspects({ ok: true, catalog_available: true, reason: "", prospects: [prospect] });
    expect(r.prospects).toEqual([prospect]);
    expect(r.catalog_available).toBe(true);
  });

  it("fills a prospect's missing aggregate and drops non-object rows", () => {
    const r = normalizeCollegeProspects({ ok: true, prospects: [{ id: "p1", name: "A" }, null, 5] });
    expect(r.prospects).toHaveLength(1);
    expect(r.prospects[0].aggregate).toEqual({ avg_grade: null, scout_count: 0, avg_round_projection: null });
    expect(r.prospects[0].on_watchlist).toBe(false);
  });

  it("fills a community trade's missing send/receive/reactions", () => {
    const r = normalizeCommunityTrades({ ok: true, trades: [{ id: "t1" }], reaction_emoji: ["x"] });
    expect(r.trades[0].send).toEqual([]);
    expect(r.trades[0].receive).toEqual([]);
    expect(r.trades[0].reactions).toEqual({});
    expect(r.trades[0].my_reactions).toEqual([]);
    expect(r.reaction_emoji).toEqual(["x"]);
  });

  it("keeps a real me payload", () => {
    const r = normalizeMe({ ok: true, user: { id: "u", email: "e@x.com", entitlement: "premium", sleeper_username: "s", profile_status: "ok", league_cap: 5 }, premium_benefits: ["a"] });
    expect(r.user).toMatchObject({ entitlement: "premium", profile_status: "ok", league_cap: 5, email: "e@x.com" });
    expect(r.premium_benefits).toEqual(["a"]);
  });
});

describe("twin", () => {
  it("mobile/src/lib/apiDefaults.ts is byte-identical", () => {
    expect(readFileSync("../mobile/src/lib/apiDefaults.ts", "utf8")).toBe(readFileSync("src/lib/apiDefaults.ts", "utf8"));
  });
});
