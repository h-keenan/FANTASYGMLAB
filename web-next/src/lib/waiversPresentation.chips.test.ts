import { describe, expect, it } from "vitest";

import { filterByRecommendation, waiverReasonChips } from "./waiversPresentation";

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

describe("filterByRecommendation", () => {
  it("filters by label", () => {
    const rows = [{ recommendation_label: "Add" }, { recommendation_label: "Stash" }];
    expect(filterByRecommendation(rows, "Stash")).toHaveLength(1);
    expect(filterByRecommendation(rows, "all")).toHaveLength(2);
  });
});
