import { describe, expect, it } from "vitest";

import { buildNewsDigest, newsHeadlineChip, newsLeaguePreview, newsVerdict, type DigestItem } from "@/lib/newsDigest";

const item = (o: Partial<DigestItem>): DigestItem => ({
  title: "Headline",
  link: null,
  source: "ESPN",
  summary: null,
  published_ts: 1,
  event_type: null,
  speculative: false,
  ...o,
});

describe("newsVerdict", () => {
  it("Start for good role/injury news on a playable player", () => {
    expect(newsVerdict(item({ event_type: "role/depth chart", title: "Gibbs expects 22 touches", roster_relationship: "starter" })).key).toBe("start");
    expect(newsVerdict(item({ event_type: "injury/status", title: "Full practice for Gibbs" })).key).toBe("start");
  });
  it("Watch for anything that can change availability, Hold for unconfirmed or no signal", () => {
    expect(newsVerdict(item({ event_type: "injury/status", title: "Lawrence questionable with ankle" })).key).toBe("watch");
    expect(newsVerdict(item({ event_type: "injury/status", title: "Full practice but questionable" })).key).toBe("watch");
    expect(newsVerdict(item({ event_type: "role/depth chart", title: "Full practice", speculative: true })).key).toBe("hold");
    expect(newsVerdict(item({ event_type: "off-field/drama", title: "Attends charity event" })).key).toBe("hold");
  });
  it("a player on IR is never a Start", () => {
    expect(newsVerdict(item({ event_type: "injury/status", title: "Full practice", roster_relationship: "ir" })).key).toBe("hold");
  });
});

describe("buildNewsDigest", () => {
  const alerts = [
    item({ title: "A", link: "a", matched_player: "Bench Guy", matched_player_id: "2", event_type: "injury/status", roster_relationship: "bench", read: true }),
    item({ title: "B", link: "b", matched_player: "Star Back", matched_player_id: "1", event_type: "role/depth chart", roster_relationship: "starter", read: false }),
  ];
  const general = [item({ title: "B", link: "b" }), item({ title: "C", link: "c", event_type: "transaction", matched_player: "Star Back", matched_player_id: "1" }), item({ title: "D", link: "d" })];

  it("puts starters first, builds the strip with unread dots and drops league items already shown as rows", () => {
    const d = buildNewsDigest({ alerts, general, filter: "all", playerKey: null });
    expect(d.rows.map((r) => r.item.title)).toEqual(["B", "A"]);
    expect(d.strip.map((p) => [p.name, p.unread])).toEqual([["Bench Guy", false], ["Star Back", true]]);
    expect(d.league.map((i) => i.title)).toEqual(["C", "D"]);
    expect(newsHeadlineChip(d)).toBe("1 affect your lineup");
    expect(newsLeaguePreview(d.league)).toBe("C and 1 more");
  });

  it("a picked player pulls his league-wide stories into his list", () => {
    const d = buildNewsDigest({ alerts, general, filter: "all", playerKey: "1" });
    expect(d.rows.map((r) => r.item.title)).toEqual(["B", "C"]);
    expect(d.league).toEqual([]);
  });

  it("filters by event type", () => {
    const d = buildNewsDigest({ alerts, general, filter: "injury", playerKey: null });
    expect(d.rows.map((r) => r.item.title)).toEqual(["A"]);
  });
});
