import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

import { TRADE_SHARE_COPY } from "./tradeCopy";

function block(source: string): string {
  const start = source.indexOf("// BEGIN TRADE_SHARE_COPY");
  const end = source.indexOf("// END TRADE_SHARE_COPY");
  return source.slice(start, end);
}

describe("trade share card copy", () => {
  it("uses the in-app Trade Hub wording", () => {
    const card = readFileSync(path.resolve(__dirname, "../../components/TradeIdeaCard.tsx"), "utf8");
    expect(card).toContain(`label="${TRADE_SHARE_COPY.send}"`);
    expect(card).toContain(`label="${TRADE_SHARE_COPY.get}"`);
    expect(card).toContain(TRADE_SHARE_COPY.balance);
  });

  it("stays byte-identical to mobile's copy", () => {
    const web = readFileSync(path.resolve(__dirname, "tradeCopy.ts"), "utf8");
    const mobile = readFileSync(path.resolve(__dirname, "../../../../mobile/src/lib/tradeShareCopy.ts"), "utf8");
    expect(block(mobile)).toBe(block(web));
    expect(block(web)).toContain("TRADE_SHARE_COPY");
  });
});
