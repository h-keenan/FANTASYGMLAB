import { describe, expect, it } from "vitest";

import { opportunityUsageCaption } from "./playerQuickViewPresentation";

const down40 = { direction: "down" as const, trend_pct: -40, confidence_label: "high confidence" };

describe("opportunityUsageCaption", () => {
  it("explains Elite Opportunity next to a confirmed usage drop", () => {
    expect(opportunityUsageCaption("Elite Opportunity", down40)).toMatch(/depth-chart role.*down 40%/);
  });
  it("stays quiet when signals agree or the drop is mild", () => {
    expect(opportunityUsageCaption("Elite Opportunity", { ...down40, direction: "up" })).toBeNull();
    expect(opportunityUsageCaption("Elite Opportunity", { direction: "down", trend_pct: -8, confidence_label: "moderate confidence" })).toBeNull();
    expect(opportunityUsageCaption("Lead Receiver", down40)).toBeNull();
    expect(opportunityUsageCaption(null, down40)).toBeNull();
  });
});
