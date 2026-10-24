import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

import { SAMPLE_ROSTER, SAMPLE_TRADE, sampleTradeVerdict } from "./sampleLeague";

describe("sampleLeague", () => {
  it("computes a deterministic verdict from summed values", () => {
    const verdict = sampleTradeVerdict(SAMPLE_TRADE);
    expect(verdict.giveTotal).toBe(92);
    expect(verdict.getTotal).toBe(90);
    expect(verdict.label).toBe("Fair");
    expect(sampleTradeVerdict({ ...SAMPLE_TRADE, get: [{ ...SAMPLE_TRADE.get[0], value: 99 }] }).label).toBe("Favors you");
    expect(sampleTradeVerdict({ ...SAMPLE_TRADE, get: [{ ...SAMPLE_TRADE.get[0], value: 10 }] }).tone).toBe("danger");
  });

  it("has unique player ids", () => {
    const ids = [...SAMPLE_ROSTER, ...SAMPLE_TRADE.get].map((p) => p.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it("stays identical to the mobile copy", () => {
    const web = readFileSync(resolve(__dirname, "sampleLeague.ts"), "utf8");
    const mobile = readFileSync(resolve(__dirname, "../../../mobile/src/lib/sampleLeague.ts"), "utf8");
    expect(mobile).toBe(web);
  });
});
