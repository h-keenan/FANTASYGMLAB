import { describe, expect, it } from "vitest";
import { tradeOutcomeChips } from "./tradeOutcomeChips";

describe("tradeOutcomeChips", () => {
  it("gain is a success chip, loss is muted (never red)", () => {
    expect(tradeOutcomeChips({ outcomeLabel: "Made it", netPts: 34, netPct: 10 })[0]).toMatchObject({ label: "You gained +34", tone: "success" });
    const loss = tradeOutcomeChips({ outcomeLabel: "Made it", netPts: -12, netPct: -4 });
    expect(loss[0]).toMatchObject({ label: "Down 12", tone: "muted" });
  });
  it("falls back to the outcome label without points", () => {
    expect(tradeOutcomeChips({ outcomeLabel: "Didn't send", netPts: null, netPct: null })).toEqual([{ key: "outcome", label: "Didn't send", tone: "muted" }]);
  });
});
