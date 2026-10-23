import { describe, expect, it } from "vitest";

import { activeTrialDays, priceWithCadence, thenPriceLine, trialCtaLabel, trialEndLabel } from "./trialCopy";

describe("trialCopy", () => {
  it("formats the price line from the real plan price", () => {
    expect(priceWithCadence({ price: "$3.99", cadence: "per month" })).toBe("$3.99/month");
    expect(thenPriceLine({ price: "$19.99", cadence: "per year" })).toBe("Then $19.99/year. Cancel anytime.");
  });
  it("only reports trial days for an eligible account", () => {
    expect(activeTrialDays({ days: 3, eligible: true })).toBe(3);
    expect(activeTrialDays({ days: 3, eligible: false })).toBe(0);
    expect(activeTrialDays(undefined)).toBe(0);
    expect(trialCtaLabel(3)).toBe("Start 3-day free trial");
  });
  it("labels only a future trial end", () => {
    const now = new Date("2026-10-22T12:00:00Z");
    expect(trialEndLabel("2026-10-25T12:00:00Z", now)).toBe("Trial ends Oct 25");
    expect(trialEndLabel("2026-10-20T12:00:00Z", now)).toBe("");
    expect(trialEndLabel("", now)).toBe("");
  });
});
