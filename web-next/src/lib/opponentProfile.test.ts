import { describe, expect, it } from "vitest";

import { firstsFlowText, hasProfileContent, offerCaption, ordinal, picksText, rankText } from "./opponentProfile";

describe("opponentProfile helpers", () => {
  it("formats ordinals including teens", () => {
    expect([1, 2, 3, 4, 11, 12, 13, 21, 22].map(ordinal)).toEqual(["1st", "2nd", "3rd", "4th", "11th", "12th", "13th", "21st", "22nd"]);
  });

  it("formats rank and pick text", () => {
    expect(rankText({ position: "RB", rank: 1, of: 12 })).toBe("RB, 1st of 12");
    expect(picksText({ rank: 2, of: 12, pick_count: 7, first_rounders: 1, firsts_acquired: 0, firsts_sent: 0 })).toBe(
      "2nd of 12 in draft capital · 7 picks · 1 first",
    );
    expect(picksText({ rank: null, of: 12, pick_count: null, first_rounders: null, firsts_acquired: 0, firsts_sent: 0 })).toBe("");
  });

  it("hides first flow when nothing moved", () => {
    expect(firstsFlowText({ rank: 1, of: 12, pick_count: 1, first_rounders: 1, firsts_acquired: 0, firsts_sent: 0 })).toBeNull();
    expect(firstsFlowText({ rank: 1, of: 12, pick_count: 1, first_rounders: 1, firsts_acquired: 2, firsts_sent: 1 })).toBe(
      "Firsts: 2 acquired, 1 traded away",
    );
  });

  it("captions the prefill by side", () => {
    expect(offerCaption({ player_id: "1", name: "A B", position: "RB", team: "KC", side: "receive" })).toContain("asking for A B");
    expect(offerCaption({ player_id: "1", name: "A B", position: "RB", team: "KC", side: "send" })).toContain("offering A B");
  });

  it("has no content for failed or not-ready responses", () => {
    expect(hasProfileContent(null)).toBe(false);
    expect(hasProfileContent({ ok: true, reason: "no_rankings_data", roster_id: "2" })).toBe(false);
    expect(hasProfileContent({ ok: true, reason: "", roster_id: "2", direction: { key: "retool", label: "Retool", rank: 1, league_size: 12, record: "1-1", confidence_label: "low" } })).toBe(true);
  });
});
