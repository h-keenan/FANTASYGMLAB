import { describe, expect, it } from "vitest";

import { pqvBioForContext, pqvRealWorld } from "./pqvContext";

describe("PQV real-world context", () => {
  it("the real Player Quick View shows everything", () => {
    expect(pqvRealWorld(false)).toEqual({ fetchNews: true, showNews: true, showAvailability: true, showDepthChartNote: true, showDepthChart: true, showInjuryHistory: true, fetchDepthChart: true, fetchInjuryHistory: true, showBye: true, showContract: true });
    const bio = { bye_week: "Week 8", contract_status: "Through 2028", college: "Ohio State" };
    expect(pqvBioForContext(bio, false)).toBe(bio);
  });
  it("inside Fantasy Sim nothing from the real world is fetched or shown (the depth chart / injury sections show the game's own data)", () => {
    const { showDepthChart, showInjuryHistory, ...rest } = pqvRealWorld(true);
    expect([showDepthChart, showInjuryHistory]).toEqual([true, true]);
    expect(Object.values(rest).every((v) => v === false)).toBe(true);
    expect(pqvBioForContext({ bye_week: "Week 8", contract_status: "Through 2028", college: "Ohio State" }, true)).toEqual({ bye_week: "", contract_status: "", college: "Ohio State" });
  });
});
