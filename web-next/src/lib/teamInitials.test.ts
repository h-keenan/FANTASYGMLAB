import { describe, expect, it } from "vitest";

import { teamInitials } from "./teamInitials";

describe("teamInitials", () => {
  it("uses the first letters of the first and last words", () => {
    expect(teamInitials("Gridiron Goats")).toBe("GG");
    expect(teamInitials("The Dynasty Destroyers")).toBe("TD");
  });
  it("takes two letters from a one-word name", () => {
    expect(teamInitials("Blitz")).toBe("BL");
  });
  it("skips emoji and symbols instead of splitting a surrogate pair", () => {
    expect(teamInitials("Gridiron Goats 🐐")).toBe("GG");
    expect(teamInitials("🐐")).toBe("");
    expect(teamInitials("🔥Fire")).toBe("FI");
    for (const char of teamInitials("Team 🏈")) expect(char.charCodeAt(0)).not.toBeGreaterThanOrEqual(0xd800);
  });
  it("handles empty and missing names", () => {
    expect(teamInitials("")).toBe("");
    expect(teamInitials(null)).toBe("");
    expect(teamInitials("   ")).toBe("");
  });
});
