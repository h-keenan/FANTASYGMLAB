import { describe, expect, it } from "vitest";

import { filterByRecommendation, waiverReasonChips, waiverReasonLine } from "./waiversPresentation";

describe("waiverReasonChips", () => {
  it("maps real catalyst and need reasons, catalysts first, capped at 2", () => {
    const chips = waiverReasonChips({
      sleeper_trending_add: true,
      faab: { reasons: ["Fills a starting WR need for you", "Usage up 40% lately", "3 teams need a WR"] },
    });
    expect(chips).toEqual(["Trending", "Usage +40%"]);
  });

  it("never invents a chip without a backing signal", () => {
    expect(waiverReasonChips({ faab: { reasons: ["Some unrelated text"] } })).toEqual([]);
    expect(waiverReasonChips({})).toEqual([]);
  });

  it("maps depth chart, role and injury cover", () => {
    expect(
      waiverReasonChips(
        { injury_replacement_fit: true, faab: { reasons: ["Moved up 2 spots on the depth chart", "Role rising"] } },
        3,
      ),
    ).toEqual(["Role rising", "Depth chart up", "Injury cover"]);
  });
});

describe("bigger upgrade chip", () => {
  it("is one short line with the lineup gain, first, and absent without the server flag", () => {
    expect(waiverReasonChips({ bigger_upgrade: true, lineup_ppw: 1.84, sleeper_trending_add: true })).toEqual([
      "Bigger than your need: +1.8 pts/wk",
      "Trending",
    ]);
    expect(waiverReasonChips({ lineup_ppw: 1.84 })).toEqual([]);
    expect(waiverReasonChips({ bigger_upgrade: true, lineup_ppw: null })).toEqual(["Bigger than your need"]);
  });
});

describe("filterByRecommendation", () => {
  it("filters by label", () => {
    const rows = [{ recommendation_label: "Add" }, { recommendation_label: "Stash" }];
    expect(filterByRecommendation(rows, "Stash")).toHaveLength(1);
    expect(filterByRecommendation(rows, "all")).toHaveLength(2);
  });
});

describe("waiverReasonLine", () => {
  it("is the top chip plus a count of the rest (chips and the usage flag)", () => {
    const line = waiverReasonLine({
      sleeper_trending_add: true,
      injury_replacement_fit: true,
      usage_flag: { label: "Role growing" },
      faab: { reasons: ["Usage up 40% lately"] },
    });
    expect(line).toEqual({ line: "Trending", more: 3 });
  });
  it("falls back to the usage flag and is empty with no signals", () => {
    expect(waiverReasonLine({ usage_flag: { label: "Role growing" } })).toEqual({ line: "Role growing", more: 0 });
    expect(waiverReasonLine({})).toEqual({ line: null, more: 0 });
  });
});
