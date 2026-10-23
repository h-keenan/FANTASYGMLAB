import { describe, expect, it } from "vitest";

import { espnUnavailableLeagueId, importedPlatformLabel, isEspnLeagueId, leagueHomePath, notAvailableMessage } from "./leaguePlatform";

const ESPN_ID = "espn:42654852:2026";
const ENCODED = encodeURIComponent(ESPN_ID);

describe("leaguePlatform", () => {
  it("recognises ESPN league ids by their prefix only", () => {
    expect(isEspnLeagueId(ESPN_ID)).toBe(true);
    expect(isEspnLeagueId("1180112345678901234")).toBe(false);
    expect(isEspnLeagueId(null)).toBe(false);
  });

  it("treats Fleaflicker and MFL leagues like ESPN leagues, with their own label", () => {
    expect(isEspnLeagueId("fleaflicker:206154:2025")).toBe(true);
    expect(isEspnLeagueId("mfl:10015:2025")).toBe(true);
    expect(isEspnLeagueId("yahoo:1:2025")).toBe(false);
    expect(importedPlatformLabel("mfl:10015:2025")).toBe("MFL");
    expect(notAvailableMessage("fleaflicker:206154:2025")).toBe("Not available for Fleaflicker leagues yet.");
    expect(espnUnavailableLeagueId(`/dashboard/${encodeURIComponent("mfl:10015:2025")}`)).toBe("mfl:10015:2025");
    expect(leagueHomePath("mfl:10015:2025", "X")).toBe(`/my-team/${encodeURIComponent("mfl:10015:2025")}?name=X`);
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
