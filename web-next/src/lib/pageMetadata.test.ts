import { describe, expect, it } from "vitest";

import { pageMetadata } from "./pageMetadata";

describe("pageMetadata", () => {
  it("names the page after its nav label", () => {
    expect(pageMetadata("waivers").title).toBe("Waivers · FantasyDesk");
    expect(pageMetadata("trade-hub").title).toBe("Trade Hub · FantasyDesk");
    expect(pageMetadata("league-rankings").title).toBe("League Rankings · FantasyDesk");
  });

  it("falls back to the brand for an unknown segment", () => {
    expect(pageMetadata("nope").title).toBe("FantasyDesk");
  });
});
