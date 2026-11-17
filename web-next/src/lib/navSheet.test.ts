import { describe, expect, it } from "vitest";

import { navSheetGroups, navSheetNoMatch, navSheetSearchCopy } from "@/lib/navSheet";

const rows = (...n: string[]) => n.map((label) => ({ label }));

describe("navSheetGroups", () => {
  it("lists league, tools, general, account inside a league, titled by the league name", () => {
    const g = navSheetGroups({ leagueName: "Revivalry", core: rows("Today"), tools: rows("Trade Hub"), general: rows("News"), account: rows("Account") });
    expect(g.map((x) => [x.id, x.title])).toEqual([["league", "Revivalry"], ["tools", "GM Tools"], ["general", "General"], ["account", "Account"]]);
  });
  it("drops the league groups outside a league and any empty group", () => {
    const g = navSheetGroups({ leagueName: null, core: rows("Today"), tools: rows("Trade Hub"), general: rows("News"), account: [] });
    expect(g.map((x) => x.id)).toEqual(["general"]);
  });
  it("falls back to League when the name is blank", () => {
    expect(navSheetGroups({ leagueName: "", core: rows("Today"), tools: [], general: [], account: [] })[0].title).toBe("League");
  });
  it("search copy and no-match text depend on having a league", () => {
    expect(navSheetSearchCopy(true).label).toMatch(/players/);
    expect(navSheetSearchCopy(false).label).not.toMatch(/players/);
    expect(navSheetNoMatch(false, " zz ")).toContain("“zz”");
  });
});
