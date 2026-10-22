import { describe, expect, it } from "vitest";

import { findManagerRow, headlineChips, sampleFill, tendencyBadgeText, tendencyTone } from "./managerTendencies";

describe("headlineChips", () => {
  it("splits a headline into chips and drops not-enough-data lead-ins", () => {
    expect(headlineChips("Targets WRs. Sells picks.")).toEqual(["Targets WRs", "Sells picks"]);
    expect(headlineChips("Not enough trades yet (2 trades).")).toEqual([]);
    expect(headlineChips("Not enough trades yet (2 trades). Sells picks.")).toEqual(["Sells picks"]);
    expect(headlineChips(null)).toEqual([]);
  });
});

describe("findManagerRow", () => {
  const data = {
    ok: true,
    is_premium: true,
    upsell: null,
    managers: [{ roster_id: 3, team_name: "Big Dogs", owner_handle: "a", headline: "x", sample: null }],
  };
  it("matches by roster id, then team name", () => {
    expect(findManagerRow(data, { rosterId: "3" })?.roster_id).toBe(3);
    expect(findManagerRow(data, { teamName: " big dogs " })?.roster_id).toBe(3);
    expect(findManagerRow(data, { teamName: "nope" })).toBeUndefined();
  });
});

describe("tendency presentation", () => {
  it("maps labels to tones and readable text", () => {
    expect(tendencyTone("contending")).toBe("success");
    expect(tendencyTone("rebuilding")).toBe("warning");
    expect(tendencyTone("unknown_thing")).toBe("accent");
    expect(tendencyBadgeText("very_active_on_waivers")).toBe("Very active on waivers");
    expect(tendencyBadgeText(null)).toBeNull();
  });
  it("caps the sample meter", () => {
    expect(sampleFill(2, 3)).toBeCloseTo(1 / 3);
    expect(sampleFill(50, 3)).toBe(1);
  });
});
