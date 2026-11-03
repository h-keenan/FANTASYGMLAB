import { describe, expect, it } from "vitest";

import { rookieBadge } from "./playerQuickViewPresentation";

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
