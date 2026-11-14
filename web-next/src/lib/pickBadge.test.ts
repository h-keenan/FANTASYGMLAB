import { describe, expect, it } from "vitest";

import { pickBadge, roundFromLabel } from "./pickBadge";

describe("pickBadge", () => {
  it("builds the round badge text", () => {
    expect(pickBadge({ round: 1, pickNo: 3 })).toEqual({ top: "R1", bottom: "#3", year: null, a11y: "Round 1 pick 3" });
    expect(pickBadge({ label: "2027 Round 1 (note)" }).top).toBe("R1");
    expect(pickBadge({ label: "2027 Round 1 (note)" }).year).toBe("2027");
    expect(roundFromLabel("2028 R2")).toBe("2");
    expect(roundFromLabel("2026 2nd round")).toBe("2");
    expect(pickBadge({}).top).toBe("PICK");
    expect(pickBadge({ pickNo: 7 }).top).toBe("#7");
  });
});
