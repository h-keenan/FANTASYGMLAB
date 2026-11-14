import { describe, expect, it } from "vitest";

import { managerProfileTabs, nextPanelMinHeight, percentileTabs } from "./sheetTabs";

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
});
