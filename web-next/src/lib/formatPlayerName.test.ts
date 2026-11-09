import { describe, expect, it } from "vitest";

import { abbreviatePlayerName, PLAYER_NAME_LENGTH_THRESHOLD, shouldAbbreviatePlayerName } from "./formatPlayerName";
import { PLAYER_NAME_FIXTURES } from "./playerNameFixtures";

describe("abbreviatePlayerName", () => {
  it.each(PLAYER_NAME_FIXTURES.map(([input, expected]) => [input, expected]))("%j -> %j", (input, expected) => {
    expect(abbreviatePlayerName(input)).toBe(expected);
  });

  it("handles null and undefined", () => {
    expect(abbreviatePlayerName(null)).toBe("");
    expect(abbreviatePlayerName(undefined)).toBe("");
  });
});

describe("shouldAbbreviatePlayerName", () => {
  it("keeps short names full and flags names over the threshold", () => {
    expect(PLAYER_NAME_LENGTH_THRESHOLD).toBe(12);
    expect(shouldAbbreviatePlayerName("Josh Allen")).toBe(false);
    expect(shouldAbbreviatePlayerName("CeeDee Lamb")).toBe(false);
    expect(shouldAbbreviatePlayerName("Juwan Johnson")).toBe(true);
    expect(shouldAbbreviatePlayerName("Quinshon Judkins")).toBe(true);
    expect(shouldAbbreviatePlayerName("Rhamondre Stevenson")).toBe(true);
  });
  it("handles empty input and custom thresholds", () => {
    expect(shouldAbbreviatePlayerName(null)).toBe(false);
    expect(shouldAbbreviatePlayerName("   ")).toBe(false);
    expect(shouldAbbreviatePlayerName("Rhamondre Stevenson", Infinity)).toBe(false);
    expect(shouldAbbreviatePlayerName("  Josh Allen ", 9)).toBe(true);
  });
});
