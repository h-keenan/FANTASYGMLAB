import { describe, expect, it } from "vitest";

import { compactSummaryText } from "./compactModule";
import { tradeIdeaGainPhrase, tradeIdeaGainText, tradeIdeaNamesText, tradeIdeaSummaryParts } from "./tradeIdeaSummary";

describe("tradeIdeaSummary", () => {
  it("reads balance, swap, fairness and confidence", () => {
    const parts = tradeIdeaSummaryParts({
      gain: 1250,
      sendNames: ["J. Gibbs"],
      receiveNames: ["C. Olave", "T. Hill", "A. Brown"],
      band: "Fair",
      confidenceLabel: "High",
    });
    expect(compactSummaryText(parts)).toBe("You gain +1,250 · J. Gibbs for C. Olave +2 · Fair · High confidence");
    expect(parts[0]).toMatchObject({ tone: "success", strong: true });
  });
  it("handles even and negative gains and missing sides", () => {
    expect(tradeIdeaGainText(0)).toBe("Even");
    expect(tradeIdeaGainText(-120.4)).toBe("-120");
    expect(tradeIdeaNamesText(["A. One", "B. Two"])).toBe("A. One + B. Two");
    expect(tradeIdeaSummaryParts({ gain: 5, sendNames: [], receiveNames: ["C. Olave"] })[1].text).toBe("Get C. Olave");
  });
  it("states the balance from the user's side and never colours a give-up red", () => {
    expect(tradeIdeaGainPhrase(662)).toBe("You gain +662");
    expect(tradeIdeaGainPhrase(-747.2)).toBe("You give up 747");
    expect(tradeIdeaGainPhrase(0)).toBe("Even");
    const down = tradeIdeaSummaryParts({ gain: -747, sendNames: ["C. Otton"], receiveNames: ["J. McMillan"] })[0];
    expect(down.text).toBe("You give up 747");
    expect(down.tone).toBe("muted");
  });
  it("is never fewer than the 12 real characters a collapsed module needs", () => {
    const text = compactSummaryText(tradeIdeaSummaryParts({ gain: 0, sendNames: ["A. B"], receiveNames: ["C. D"] }));
    expect(text.length).toBeGreaterThanOrEqual(12);
  });
});
