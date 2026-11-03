import { describe, expect, it } from "vitest";

import type { TradeTargetOffer } from "@/lib/api";
import { canBuildOffer, offerAnalyzerHref, offerBuilderHref, offerPrefillFromSearch } from "@/lib/tradeOffer";

const offer: Pick<TradeTargetOffer, "send" | "receive"> = {
  send: [
    { kind: "player", id: "p1", label: "A", position: "WR", value: 1 },
    { kind: "pick", id: "2027:2:4", label: "2027 Round 2", position: "PICK", value: 1 },
  ],
  receive: [{ kind: "player", id: "t1", label: "Target", position: "RB", value: 1 }],
};

describe("tradeOffer links", () => {
  it("builder link carries the target", () => {
    expect(offerBuilderHref("L 1", "My League", "t1")).toBe("/trade-offer/L%201?name=My+League&playerId=t1");
  });

  it("round-trips an offer into the Analyzer prefill", () => {
    const href = offerAnalyzerHref("L1", "My League", offer);
    expect(href.startsWith("/trade-analyzer/L1?")).toBe(true);
    const params = new URL(href, "https://x.test").searchParams;
    expect(offerPrefillFromSearch(params)).toEqual({
      send: ["p1"],
      receive: ["t1"],
      sendPicks: ["2027:2:4"],
      receivePicks: [],
    });
  });

  it("is not a prefill when nothing comes back", () => {
    expect(offerPrefillFromSearch(new URLSearchParams("send=p1"))).toBeNull();
    expect(offerPrefillFromSearch(new URLSearchParams("name=x"))).toBeNull();
  });
});

describe("canBuildOffer", () => {
  const ownership = { myPlayerIds: new Set(["mine"]), rosteredPlayerIds: new Set(["mine", "theirs"]) };
  it("only for players on another roster", () => {
    expect(canBuildOffer("theirs", ownership)).toBe(true);
    expect(canBuildOffer("mine", ownership)).toBe(false);
    expect(canBuildOffer("free-agent", ownership)).toBe(false);
    expect(canBuildOffer("theirs", null)).toBe(false);
    expect(canBuildOffer("", ownership)).toBe(false);
  });
});
