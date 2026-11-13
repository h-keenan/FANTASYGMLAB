import { describe, expect, it } from "vitest";

import { shellActiveTab, shellBarVisible, shellNavEnabled, shellNavQueryToStore, shellParent, shellTabs } from "./shellNav";

describe("shellNavEnabled (feature flag)", () => {
  it("defaults to founder-only", () => {
    expect(shellNavEnabled({ isFounder: true })).toBe(true);
    expect(shellNavEnabled({ isFounder: false })).toBe(false);
  });
  it("?nav=bottom turns it on for anyone and ?nav=off turns it off for the founder", () => {
    expect(shellNavEnabled({ isFounder: false, queryNav: "bottom" })).toBe(true);
    expect(shellNavEnabled({ isFounder: true, queryNav: "off" })).toBe(false);
  });
  it("a remembered choice beats the default; the query beats the remembered choice", () => {
    expect(shellNavEnabled({ isFounder: false, stored: "bottom" })).toBe(true);
    expect(shellNavEnabled({ isFounder: true, stored: "off" })).toBe(false);
    expect(shellNavEnabled({ isFounder: true, stored: "off", queryNav: "bottom" })).toBe(true);
  });
  it("env on opens it to everyone, env off is a kill switch nothing overrides", () => {
    expect(shellNavEnabled({ isFounder: false, env: "on" })).toBe(true);
    expect(shellNavEnabled({ isFounder: true, env: "off", queryNav: "bottom", stored: "bottom" })).toBe(false);
  });
  it("only real choices are remembered", () => {
    expect(shellNavQueryToStore("bottom")).toBe("bottom");
    expect(shellNavQueryToStore("off")).toBe("off");
    expect(shellNavQueryToStore("x")).toBeNull();
    expect(shellNavQueryToStore(null)).toBeNull();
  });
});

describe("shellTabs", () => {
  it("is Today / Team / Trades / League / More inside a league, with the league in every link", () => {
    const tabs = shellTabs({ leagueId: "L1", leagueName: "My League" });
    expect(tabs.map((t) => t.label)).toEqual(["Today", "Team", "Trades", "League", "More"]);
    expect(tabs[0].href).toBe("/dashboard/L1?name=My%20League");
    expect(tabs[4].href).toBeUndefined();
  });
  it("is Home / Portfolio / Fantasy Sim / News / More outside a league", () => {
    expect(shellTabs({ leagueId: null, leagueName: "" }).map((t) => t.label)).toEqual(["Home", "Portfolio", "Fantasy Sim", "News", "More"]);
  });
});

describe("route to tab mapping", () => {
  it.each([
    ["/dashboard/L1", "today"],
    ["/alerts/L1", "today"],
    ["/my-team/L1", "team"],
    ["/waivers/L1", "team"],
    ["/players/L1", "team"],
    ["/gm-plan/L1", "team"],
    ["/trade-hub/L1", "trades"],
    ["/trade-analyzer/L1", "trades"],
    ["/league-rankings/L1", "league"],
    ["/games/L1", "league"],
    ["/account", "more"],
  ])("%s lights %s inside a league", (path, tab) => {
    expect(shellActiveTab(path, path !== "/account")).toBe(tab);
  });
  it("maps the league-less pages", () => {
    expect(shellActiveTab("/", false)).toBe("home");
    expect(shellActiveTab("/portfolio", false)).toBe("portfolio");
    expect(shellActiveTab("/gm-game", false)).toBe("sim");
    expect(shellActiveTab("/news", false)).toBe("news");
    expect(shellActiveTab("/premium", false)).toBe("more");
  });
});

describe("shellBarVisible", () => {
  const base = { enabled: true, signedIn: true, pathname: "/dashboard/L1" };
  it("shows on a signed-in page with the flag on", () => expect(shellBarVisible(base)).toBe(true));
  it("hides when off, signed out, on the onboarding root, or in the game (it owns its chrome)", () => {
    expect(shellBarVisible({ ...base, enabled: false })).toBe(false);
    expect(shellBarVisible({ ...base, signedIn: false })).toBe(false);
    expect(shellBarVisible({ ...base, pathname: "/" })).toBe(false);
    expect(shellBarVisible({ ...base, pathname: "/gm-game" })).toBe(false);
  });
});

describe("shellParent (back label)", () => {
  const ctx = { leagueId: "L1", leagueName: "My League" };
  it("names the parent page", () => {
    expect(shellParent("/trade-analyzer/L1", ctx)).toEqual({ label: "Trade Hub", href: "/trade-hub/L1?name=My%20League" });
    expect(shellParent("/players/L1/4046", ctx)?.label).toBe("Players");
    expect(shellParent("/waivers/L1", ctx)?.label).toBe("Today");
    expect(shellParent("/account", { leagueId: null, leagueName: "" })).toEqual({ label: "Home", href: "/" });
  });
  it("has no back on a tab root or in the game", () => {
    expect(shellParent("/dashboard/L1", ctx)).toBeNull();
    expect(shellParent("/trade-hub/L1", ctx)).toBeNull();
    expect(shellParent("/gm-game", { leagueId: null, leagueName: "" })).toBeNull();
  });
});
