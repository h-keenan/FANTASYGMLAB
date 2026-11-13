import { describe, expect, it } from "vitest";

import { activeBottomTab, bottomTabAriaLabel, bottomTabBadgeText, pathOwnsPhoneChrome, simCompactSeason, simCompactWeek, simGameBottomTabs, simStatusChips } from "./bottomNav";

describe("bottom tab badges", () => {
  it("hides zero/undefined, caps at 9+", () => {
    expect(bottomTabBadgeText(0)).toBeNull();
    expect(bottomTabBadgeText(undefined)).toBeNull();
    expect(bottomTabBadgeText(1)).toBe("1");
    expect(bottomTabBadgeText(12)).toBe("9+");
  });
  it("reads the count in the accessible name", () => {
    expect(bottomTabAriaLabel({ label: "Trades", badge: 2 })).toBe("Trades, 2 new");
    expect(bottomTabAriaLabel({ label: "Team" })).toBe("Team");
  });
});

describe("game tabs", () => {
  it("has five in season with the inbox on Trades, four in the offseason", () => {
    const tabs = simGameBottomTabs({ inbox: 3 });
    expect(tabs.map((t) => t.key)).toEqual(["home", "team", "players", "trades", "league"]);
    expect(tabs.find((t) => t.key === "trades")?.badge).toBe(3);
    const off = simGameBottomTabs({ offseason: true });
    expect(off.map((t) => t.key)).toEqual(["home", "team", "trades", "league"]);
    expect(off[0].label).toBe("Offseason");
  });
  it("falls back to the first tab for an unknown key (the desktop-only More tab)", () => {
    expect(activeBottomTab(simGameBottomTabs({}), "more")).toBe("home");
    expect(activeBottomTab(simGameBottomTabs({}), "league")).toBe("league");
  });
});

describe("status chips and compact labels", () => {
  it("turns the pre-advance notes into chips that point at the fixing tab", () => {
    expect(simStatusChips({ lineup_warnings: 1, inbox: 1 })).toEqual([
      { key: "lineup", label: "1 lineup issue", tone: "warning", tab: "team" },
      { key: "offers", label: "1 offer expiring", tone: "accent", tab: "trades" },
    ]);
    expect(simStatusChips({ lineup_warnings: 0, inbox: 0 })).toEqual([]);
    expect(simStatusChips(null)).toEqual([]);
  });
  it("formats the one-line header", () => {
    expect(simCompactWeek({ phase: "regular", week: 3, settings: { regular_weeks: 14 } })).toBe("Wk 3/14");
    expect(simCompactWeek({ phase: "playoffs", week: 15 })).toBe("Playoffs Wk 15");
    expect(simCompactSeason({ season_no: 1, seasons: 5 })).toBe("S1/5");
    expect(simCompactSeason(null)).toBe("");
  });
});

describe("route ownership", () => {
  it("only the game owns phone chrome in phase A", () => {
    expect(pathOwnsPhoneChrome("/gm-game")).toBe(true);
    expect(pathOwnsPhoneChrome("/gm-game/")).toBe(true);
    expect(pathOwnsPhoneChrome("/fantasy-sim/abc")).toBe(false);
    expect(pathOwnsPhoneChrome("/dashboard/1")).toBe(false);
    expect(pathOwnsPhoneChrome(null)).toBe(false);
  });
});

import { simOrbAriaLabel } from "./bottomNav";
describe("game orb label", () => {
  it("adds pending offers to the name", () => {
    expect(simOrbAriaLabel("Home", 0)).toBe("Game menu, Home");
    expect(simOrbAriaLabel("Home", 1)).toBe("Game menu, Home. 1 trade offer waiting");
  });
});
