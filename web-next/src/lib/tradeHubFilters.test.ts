import { describe, expect, it } from "vitest";

import type { TradeIdea } from "@/lib/api";
import { boardPositions, filterTradeIdeas, ideaTags, impactTagCounts, shortReason } from "@/lib/tradeHubFilters";

function idea(over: Partial<TradeIdea> & { send?: string[]; receive?: string[] }): TradeIdea {
  return {
    partner_team_name: "T",
    rationale: "",
    trade_gain: 0,
    confidence_label: "High",
    market_realism_label: "High",
    reasoning_tags: [],
    package: {
      send: (over.send ?? ["RB"]).map((position) => ({ asset_type: "player", position })),
      receive: (over.receive ?? ["WR"]).map((position) => ({ asset_type: "player", position })),
      value_edge: "",
      confidence: "",
    },
    category: "",
    value_edge_band: "Fair",
    impact_tag: "",
    landed_gm_target_player_ids: [],
    send_score: 0,
    receive_score: 0,
    ...over,
  } as TradeIdea;
}

describe("tradeHubFilters", () => {
  const ideas = [
    idea({ impact_tag: "buy_low", receive: ["TE"] }),
    idea({ impact_tag: "sell_high" }),
    idea({ impact_tag: "", send: ["QB"] }),
  ];

  it("filters by impact tag and position together", () => {
    expect(filterTradeIdeas(ideas, { impact: null, position: null })).toHaveLength(3);
    expect(filterTradeIdeas(ideas, { impact: "buy_low", position: null })).toHaveLength(1);
    expect(filterTradeIdeas(ideas, { impact: null, position: "QB" })).toHaveLength(1);
    expect(filterTradeIdeas(ideas, { impact: "sell_high", position: "TE" })).toHaveLength(0);
  });

  it("lists board positions in a stable order", () => {
    expect(boardPositions(ideas)).toEqual(["QB", "RB", "WR", "TE"]);
  });

  it("counts only impact tags the engine produced", () => {
    expect(impactTagCounts(ideas).map((entry) => [entry.tag, entry.count])).toEqual([
      ["buy_low", 1],
      ["sell_high", 1],
    ]);
  });

  it("maps tags only from engine category and impact tag", () => {
    expect(ideaTags(idea({ category: "Headline Recommendation", impact_tag: "buy_low" })).map((t) => t.label)).toEqual([
      "Headline Recommendation",
      "Buy Low",
    ]);
    expect(ideaTags(idea({}))).toEqual([]);
  });

  it("keeps one short reason sentence", () => {
    expect(shortReason("Fills your RB need. Also young.")).toBe("Fills your RB need.");
    expect(shortReason("")).toBe("");
  });
});
