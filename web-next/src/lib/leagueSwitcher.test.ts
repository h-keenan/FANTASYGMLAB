import { describe, expect, it } from "vitest";

import { swapLeagueIdInPath } from "./leagueSwitcher";

describe("swapLeagueIdInPath", () => {
  it("swaps the league id segment while keeping the rest of the path", () => {
    expect(swapLeagueIdInPath("/waivers/OLD_ID", "OLD_ID", "NEW_ID")).toBe("/waivers/NEW_ID");
  });

  it("keeps the current route for deeper nested-looking routes too", () => {
    expect(swapLeagueIdInPath("/trade-analyzer/OLD_ID", "OLD_ID", "NEW_ID")).toBe("/trade-analyzer/NEW_ID");
  });

  it("falls back to /dashboard when the league id isn't found in the path", () => {
    expect(swapLeagueIdInPath("/portfolio", "OLD_ID", "NEW_ID")).toBe("/dashboard/NEW_ID");
  });

  it("percent-encodes both the matched segment and the replacement", () => {
    expect(swapLeagueIdInPath(`/waivers/${encodeURIComponent("old id")}`, "old id", "new id")).toBe(
      `/waivers/${encodeURIComponent("new id")}`,
    );
  });
});
