import { describe, expect, it } from "vitest";

import { abbreviatePlayerName } from "./formatPlayerName";
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
