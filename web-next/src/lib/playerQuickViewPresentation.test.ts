import { describe, expect, it } from "vitest";

import { opportunityLabelTone, rookieBadge, usageTrendSummary, usageWindowLabel } from "./playerQuickViewPresentation";

describe("rookieBadge", () => {
  it("only shows for is_rookie true", () => {
    expect(rookieBadge(null)).toBeNull();
    expect(rookieBadge({ is_rookie: false, draft_capital: "2025 / Round 1" })).toBeNull();
    expect(rookieBadge({})).toBeNull();
  });

  it("is just ROOKIE when there is no draft data (nothing invented)", () => {
    expect(rookieBadge({ is_rookie: true, draft_capital: "", college: "" })).toEqual({ label: "ROOKIE", detail: null });
  });

  it("builds a one-line detail from real fields", () => {
    expect(rookieBadge({ is_rookie: true, draft_capital: "2026 / Round 1 / Pick 12", college: "Ohio State" })).toEqual({
      label: "ROOKIE",
      detail: "2026 · Round 1 · Pick 12 · Ohio State",
    });
    expect(rookieBadge({ is_rookie: true, college: "Ohio State" })).toEqual({ label: "ROOKIE", detail: "Ohio State" });
  });
});

describe("opportunityLabelTone", () => {
  it("maps role labels to semantic tones", () => {
    expect(opportunityLabelTone("Starter At Risk")).toBe("warning");
    expect(opportunityLabelTone("Elite Opportunity")).toBe("success");
    expect(opportunityLabelTone("Committee Back")).toBe("muted");
    expect(opportunityLabelTone(null)).toBe("muted");
  });
});

describe("usage trend window label", () => {
  it("says which window the percentage covers, from the server's own window", () => {
    expect(usageTrendSummary({ arrow: "▲", trend_pct: 8, window: 4 })).toBe("▲ 8% last 4 gm");
    expect(usageTrendSummary({ arrow: "▼", trend_pct: -12 })).toBe("▼ 12% recent");
    expect(usageWindowLabel({ window: 0 })).toBe("recent");
  });
});
