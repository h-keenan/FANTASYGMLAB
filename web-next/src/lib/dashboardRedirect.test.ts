import { describe, expect, it } from "vitest";

import { dashboardRedirectTarget } from "./dashboardRedirect";
import { leagueHomePath } from "./leaguePlatform";

const a = { league_id: "1", league_name: "A" };
const b = { league_id: "2", league_name: "B" };

describe("dashboardRedirectTarget", () => {
  it("signed out goes to the landing page", () => expect(dashboardRedirectTarget(false, [a], null)).toBe("/"));
  it("no leagues goes to connect-league", () => expect(dashboardRedirectTarget(true, [], null)).toBe("/connect-league"));
  it("one league goes to it", () => expect(dashboardRedirectTarget(true, [a], null)).toBe(leagueHomePath("1", "A")));
  it("prefers the last league", () => expect(dashboardRedirectTarget(true, [a, b], "2")).toBe(leagueHomePath("2", "B")));
  it("falls back to the first when last is unknown", () => expect(dashboardRedirectTarget(true, [a, b], "9")).toBe(leagueHomePath("1", "A")));
});
