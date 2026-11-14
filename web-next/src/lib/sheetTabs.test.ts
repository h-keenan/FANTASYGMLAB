import { describe, expect, it } from "vitest";

import { chromeDock, managerProfileTabs, nextPanelMinHeight, percentileTabs, stickyTabsOffset } from "./sheetTabs";

describe("sheetTabs", () => {
  it("manager profile always has Overview and drops empty tabs", () => {
    expect(managerProfileTabs({ hasProfile: false, tendencyCount: 0, tradeCount: 0 }).map((t) => t.key)).toEqual(["overview"]);
    expect(managerProfileTabs({ hasProfile: true, tendencyCount: 4, tradeCount: 0 }).map((t) => t.key)).toEqual(["overview", "tendencies"]);
    expect(managerProfileTabs({ hasProfile: true, tendencyCount: 4, tradeCount: 2 }).map((t) => t.label)).toEqual(["Overview", "Tendencies", "Trades"]);
  });

  it("percentile tabs follow what is loaded", () => {
    expect(percentileTabs({ hasFullPool: false, mineCount: 0 })).toEqual([]);
    expect(percentileTabs({ hasFullPool: true, mineCount: 0 }).map((t) => t.key)).toEqual(["bucket", "find"]);
    expect(percentileTabs({ hasFullPool: true, mineCount: 2 }).map((t) => t.key)).toEqual(["bucket", "find", "mine"]);
    expect(percentileTabs({ hasFullPool: false, mineCount: 2 }).map((t) => t.key)).toEqual(["mine"]);
  });

  it("panel min height only grows and ignores bad measurements", () => {
    expect(nextPanelMinHeight(0, 120.2)).toBe(121);
    expect(nextPanelMinHeight(300, 120)).toBe(300);
    expect(nextPanelMinHeight(300, NaN)).toBe(300);
    expect(nextPanelMinHeight(300, 0)).toBe(300);
  });

  it("sticky strip docks flush: top subtracts the container padding, the dock is added", () => {
    expect(stickyTabsOffset(24, 0)).toEqual({ top: -24, mask: 0 });
    expect(stickyTabsOffset(24, 40)).toEqual({ top: 16, mask: 40 });
    expect(stickyTabsOffset(NaN, -3)).toEqual({ top: 0, mask: 0 });
    expect(chromeDock(52, 44)).toBe(12);
    expect(chromeDock(40, 44)).toBe(0);
  });
});
