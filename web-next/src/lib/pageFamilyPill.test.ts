import { describe, expect, it } from "vitest";

import { familyPillContext, routeFamilyPillContext } from "./pageFamilyPill";

describe("pageFamilyPill", () => {
  it("derives the family context from the route alone (no page needed)", () => {
    const c = routeFamilyPillContext("/trade-finder/9", "9", "My League");
    expect(c?.id).toBe("family:trades");
    expect(c?.activeKey).toBe("trade_finder");
    expect(c?.tabs.map((t) => t.label)).toEqual(["Hub", "Finder", "Analyzer", "History"]);
    expect(c?.primary?.href).toBe("/trade-analyzer/9?name=My%20League");
    expect(routeFamilyPillContext("/league-recaps/9", "9", "L")?.activeKey).toBe("recaps");
    expect(routeFamilyPillContext("/waivers/9", "9", "L")?.id).toBe("family:team");
  });
  it("is null outside the families or without a league", () => {
    expect(routeFamilyPillContext("/dashboard/9", "9", "L")).toBeNull();
    expect(routeFamilyPillContext("/trade-hub/9", null, "")).toBeNull();
  });
  it("keeps Trade History account-wide with the league as a query", () => {
    expect(familyPillContext("trades", "trade_history", "9", "L").tabs.find((t) => t.key === "trade_history")?.href).toBe("/trade-history?league=9&name=L");
    expect(routeFamilyPillContext("/trade-history", "9", "L")?.activeKey).toBe("trade_history");
  });
});
