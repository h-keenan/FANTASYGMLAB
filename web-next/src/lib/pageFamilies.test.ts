import { describe, expect, it } from "vitest";

import { NAV_PAGES } from "./navCatalog";
import { activePageTab, pageTabFamily, pageTabForSegment, PAGE_TAB_FAMILIES } from "./pageFamilies";
import { shellActiveTab } from "./shellNav";

describe("page tab families", () => {
  it("lists the consolidated tabs in order", () => {
    expect(pageTabFamily("trades").tabs.map((t) => t.label)).toEqual(["Hub", "Finder", "Analyzer", "History"]);
    expect(pageTabFamily("team").tabs.map((t) => t.label)).toEqual(["Roster", "Players", "Waivers", "Matchup"]);
    expect(pageTabFamily("league").tabs.map((t) => t.label)).toEqual(["Rankings", "Recaps", "Games"]);
  });
  it("never lists a segment twice", () => {
    const segments = PAGE_TAB_FAMILIES.flatMap((f) => f.tabs.map((t) => t.segment));
    expect(new Set(segments).size).toBe(segments.length);
  });
  it("keeps the nav-active mapping: every member segment lights its family's bottom-bar tab", () => {
    for (const family of PAGE_TAB_FAMILIES) {
      for (const tab of family.tabs) expect(shellActiveTab(`/${tab.segment}/123`, true)).toBe(family.shellTab);
    }
  });
  it("only references real nav pages or the known tab routes", () => {
    const known = new Set([...NAV_PAGES.map((p) => p.key), "trade-finder", "trade-analyzer", "trade-history"]);
    for (const family of PAGE_TAB_FAMILIES) for (const tab of family.tabs) expect(known.has(tab.segment)).toBe(true);
  });
  it("resolves a segment to its family and tab", () => {
    expect(pageTabForSegment("waivers")?.family.key).toBe("team");
    expect(pageTabForSegment("games")?.tab.key).toBe("games");
    expect(pageTabForSegment("dashboard")).toBeNull();
  });
  it("falls back to the first tab for an unknown key", () => {
    expect(activePageTab(pageTabFamily("team"), "nope")).toBe("roster");
    expect(activePageTab(pageTabFamily("team"), "matchup")).toBe("matchup");
  });
});
