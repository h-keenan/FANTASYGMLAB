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
    expect(simCompactSeason({ season_no: 3, seasons: 10, year: 2028 })).toBe("S3 2028");
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
    expect(simOrbAriaLabel("Home", 0)).toBe("Home. Game menu");
    // The name starts with what the orb shows (page, then badge): WCAG 2.5.3 Label in Name.
    expect(simOrbAriaLabel("Home", 1)).toBe("Home 1. Game menu, 1 trade offer waiting");
    expect(simOrbAriaLabel("Home", 12)).toBe("Home 9+. Game menu, 12 trade offers waiting");
  });
});

describe("smart pill context helpers", () => {
  const base = { id: "t", label: "T", activeKey: "a", onSelect: () => {} };
  it("normalizes: caps tabs, drops unnamed, falls back to the first tab, null when empty", async () => {
    const { normalizePillContext, PILL_MAX_TABS } = await import("./bottomNav");
    const many = Array.from({ length: 9 }, (_, i) => ({ key: `k${i}`, label: `L${i}` }));
    expect(normalizePillContext({ ...base, tabs: many, activeKey: "k1" })?.tabs).toHaveLength(PILL_MAX_TABS);
    expect(normalizePillContext({ ...base, tabs: [{ key: "x", label: "X" }], activeKey: "zzz" })?.activeKey).toBe("x");
    expect(normalizePillContext({ ...base, tabs: [{ key: "", label: "" }] })).toBeNull();
    expect(normalizePillContext(null)).toBeNull();
    expect(normalizePillContext({ ...base, tabs: [], primary: { key: "p", label: "Go", onPress: () => {} } })).not.toBeNull();
  });
  it("modes and active index", async () => {
    const { pillMode, pillActiveIndex } = await import("./bottomNav");
    expect(pillMode(false, true)).toBe("global");
    expect(pillMode(true, false)).toBe("context");
    expect(pillMode(true, true)).toBe("menu");
    expect(pillActiveIndex({ tabs: [{ key: "a", label: "A" }, { key: "b", label: "B" }], activeKey: "b" })).toBe(1);
  });
});
