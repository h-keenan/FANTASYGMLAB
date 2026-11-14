import { describe, expect, it } from "vitest";

import { insightHref } from "@/lib/insightHref";
import { INSIGHT_TARGETS, insightAnchor, insightAriaLabel, rankBoardAnchor, type InsightKey } from "@/lib/insightLinks";
import { NAV_PAGES } from "@/lib/navCatalog";
import { RANK_BOARD_CONFIG } from "@/lib/leagueRankingsPresentation";

describe("insight -> destination map", () => {
  it("sends every insight to a real league-scoped nav page", () => {
    for (const [key, target] of Object.entries(INSIGHT_TARGETS)) {
      const page = NAV_PAGES.find((candidate) => candidate.key === target.page);
      expect(page, key).toBeDefined();
      expect(page?.leagueScoped, key).toBe(true);
      expect(target.label.length, key).toBeGreaterThan(0);
    }
  });

  it("every rank metric has a board on League Rankings (web page renders one per metric)", () => {
    for (const target of Object.values(INSIGHT_TARGETS)) {
      if (target.metric) expect(RANK_BOARD_CONFIG[target.metric]).toBeDefined();
    }
  });

  it("the Roster Age insight lands on the age rank board", () => {
    expect(insightAnchor("age")).toBe(rankBoardAnchor("age"));
    expect(insightHref("age", { id: "123", name: "My League" })).toBe("/league-rankings/123?name=My%20League#board-age");
  });

  it("encodes the league and omits the anchor for page-level targets", () => {
    expect(insightHref("injury", { id: "a/b", name: "X & Y" })).toBe("/alerts/a%2Fb?name=X%20%26%20Y");
  });

  it("composes a screen-reader name that states the fact then the destination", () => {
    expect(insightAriaLabel("age", ["Avg Age", "26.1", null, "League avg 25.2"])).toBe(
      "Avg Age, 26.1, League avg 25.2, open the Roster Age rankings",
    );
  });

  it("covers every key exactly once", () => {
    const keys = Object.keys(INSIGHT_TARGETS) as InsightKey[];
    expect(new Set(keys).size).toBe(keys.length);
  });
});
