import { describe, expect, it } from "vitest";

import { espnUnavailableLeagueId, isEspnLeagueId, leagueHomePath } from "./leaguePlatform";

const ESPN_ID = "espn:42654852:2026";
const ENCODED = encodeURIComponent(ESPN_ID);

describe("leaguePlatform", () => {
  it("recognises ESPN league ids by their prefix only", () => {
    expect(isEspnLeagueId(ESPN_ID)).toBe(true);
    expect(isEspnLeagueId("1180112345678901234")).toBe(false);
    expect(isEspnLeagueId(null)).toBe(false);
  });

  it("keeps ESPN leagues off pages they can't feed, for encoded and raw ids", () => {
    expect(espnUnavailableLeagueId(`/dashboard/${ENCODED}`)).toBe(ESPN_ID);
    expect(espnUnavailableLeagueId(`/waivers/${ESPN_ID}`)).toBe(ESPN_ID);
    expect(espnUnavailableLeagueId(`/trade-hub/${ENCODED}`)).toBe(ESPN_ID);
  });

  it("lets ESPN leagues open the supported pages, and never gates Sleeper leagues", () => {
    expect(espnUnavailableLeagueId(`/my-team/${ENCODED}`)).toBeNull();
    expect(espnUnavailableLeagueId(`/trade-analyzer/${ENCODED}`)).toBeNull();
    expect(espnUnavailableLeagueId(`/players/${ENCODED}/9221`)).toBeNull();
    expect(espnUnavailableLeagueId(`/league-rankings/${ENCODED}`)).toBeNull();
    expect(espnUnavailableLeagueId("/dashboard/1180112345678901234")).toBeNull();
    expect(espnUnavailableLeagueId("/portfolio")).toBeNull();
    expect(espnUnavailableLeagueId("/")).toBeNull();
  });

  it("opens Sleeper leagues on Dashboard and ESPN leagues on My Team", () => {
    expect(leagueHomePath("123", "Dynasty")).toBe("/dashboard/123?name=Dynasty");
    expect(leagueHomePath(ESPN_ID, "FFLR Test League")).toBe(`/my-team/${ENCODED}?name=FFLR%20Test%20League`);
  });
});

describe("espnImportFailureResult", () => {
  it("maps reasons to privacy-safe analytics results", async () => {
    const { espnImportFailureResult } = await import("./leaguePlatform");
    expect(espnImportFailureResult("private_league")).toBe("espn_private");
    expect(espnImportFailureResult("league_not_found")).toBe("espn_not_found");
    expect(espnImportFailureResult("espn_unavailable")).toBe("espn_error");
    expect(espnImportFailureResult(undefined)).toBe("espn_error");
  });
});
