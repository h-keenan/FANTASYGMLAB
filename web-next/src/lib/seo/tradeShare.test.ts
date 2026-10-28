import { describe, expect, it } from "vitest";

import type { TradeBoard } from "./tradeAnalyzer";
import { buildPublicTradeCard, publicTradeOgImageUrl, shareLinkWithUtm } from "./tradeShare";

const BOARD: TradeBoard = {
  updated: "2026-10-27",
  tepAvailable: true,
  players: [
    { id: "1", name: "Star WR", pos: "WR", team: "MIN", age: 25, inj: null, v: [9000, 9100, 9200, 9300] },
    { id: "2", name: "Solid RB", pos: "RB", team: "SF", age: 27, inj: null, v: [5000, 5100, 5200, 5300] },
  ],
};
const state = (a: string[], b: string[], f: "1qb" | "superflex" = "1qb", tep = false) => ({
  a,
  b,
  settings: { format: f, tep },
});

describe("public trade share card data", () => {
  it("uses the selected format's public values and a value-check pitch", () => {
    const card = buildPublicTradeCard(state(["1"], ["2"], "superflex"), BOARD)!;
    expect(card.idea.send_score).toBe(9100);
    expect(card.idea.receive_score).toBe(5100);
    expect(card.idea.package.send[0]).toMatchObject({ asset_type: "player", player_id: "1", name: "Star WR", score: 9100 });
    expect(card.pitch.eyebrow).toBe("Value check");
    expect(card.pitch.headline).toBe("Lopsided against you");
    expect(card.pitch.lines.join(" ")).toMatch(/Superflex/);
  });

  it("applies tight-end premium only when the board has it", () => {
    expect(buildPublicTradeCard(state(["1"], ["2"], "1qb", true), BOARD)!.idea.send_score).toBe(9200);
    const noTep = { ...BOARD, tepAvailable: false };
    expect(buildPublicTradeCard(state(["1"], ["2"], "1qb", true), noTep)!.idea.send_score).toBe(9000);
  });

  it("returns null when a side has no player on the board", () => {
    expect(buildPublicTradeCard(state(["999"], ["2"]), BOARD)).toBeNull();
    expect(buildPublicTradeCard(state(["1"], []), BOARD)).toBeNull();
  });

  it("builds the OG url only for a complete trade", () => {
    expect(publicTradeOgImageUrl(state(["1"], ["2", "3"], "superflex"))).toBe(
      "https://app.fantasygmlab.com/share-card/public-trade?a=1&b=2,3&f=sf",
    );
    expect(publicTradeOgImageUrl(state(["1"], []))).toBeNull();
  });

  it("tags a copied link with first-party utm tokens without overwriting existing ones", () => {
    const tagged = shareLinkWithUtm("https://app.fantasygmlab.com/trade-analyzer?a=1&b=2,3");
    expect(tagged).toBe(
      "https://app.fantasygmlab.com/trade-analyzer?a=1&b=2,3&utm_source=share&utm_medium=copy_link&utm_campaign=public_trade_analyzer",
    );
    expect(shareLinkWithUtm("https://x.test/trade-analyzer?a=1&utm_source=reddit")).toContain("utm_source=reddit");
  });
});
