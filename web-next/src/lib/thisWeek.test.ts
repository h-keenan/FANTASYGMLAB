import { describe, expect, it } from "vitest";

import type { ThisWeek } from "@/lib/api";
import { thisWeekTradeIdeaHeadline } from "./thisWeek";

const base: ThisWeek = { mode: "in_season", week: 7, next_action: null, rows: [] };

describe("thisWeekTradeIdeaHeadline", () => {
  it("returns the headline of an Idea trade row", () => {
    const data: ThisWeek = {
      ...base,
      rows: [{ key: "trade", status: "Idea", tone: "trade", headline: " Deebo Samuel Sr. ", why: "w", cta_label: "See the trade", route: "trade_hub", player_id: "1" }],
    };
    expect(thisWeekTradeIdeaHeadline(data)).toBe("Deebo Samuel Sr.");
  });

  it("is empty for a Hold verdict, other rows, or no data", () => {
    const hold: ThisWeek = {
      ...base,
      rows: [{ key: "trade", status: "Hold", tone: "neutral", headline: "Hold: no trade improves your team", why: "w", cta_label: null, route: null, player_id: "" }],
    };
    expect(thisWeekTradeIdeaHeadline(hold)).toBe("");
    expect(thisWeekTradeIdeaHeadline(base)).toBe("");
    expect(thisWeekTradeIdeaHeadline(null)).toBe("");
  });
});
