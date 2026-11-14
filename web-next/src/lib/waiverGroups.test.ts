import { describe, expect, it } from "vitest";

import { sharedBidNote, sharedDropCandidate } from "./waiverGroups";

describe("sharedDropCandidate (one group-level cut instead of one per row)", () => {
  const row = (id: string | null) => ({ drop_suggestion: id ? { drop: { player_id: id } } : { drop: null } });
  it("finds the cut most rows share", () => {
    const found = sharedDropCandidate([row("a"), row("a"), row("a"), row("b")]);
    expect(found?.playerId).toBe("a");
    expect(found?.count).toBe(3);
  });
  it("needs at least two rows and at least half of the rows that carry a cut", () => {
    expect(sharedDropCandidate([row("a")])).toBeNull();
    expect(sharedDropCandidate([row("a"), row("b")])).toBeNull();
    expect(sharedDropCandidate([row("a"), row("a"), row("b"), row("c"), row("d")])).toBeNull();
    expect(sharedDropCandidate([row(null), row(null)])).toBeNull();
  });
});

describe("sharedBidNote", () => {
  const bid = (remaining: number) => ({ faab: { applicable: true, dollars_known: true, remaining } });
  it("returns the shared remaining-budget line, or null when rows differ", () => {
    expect(sharedBidNote([bid(81), bid(81)])).toBe("of $81 remaining");
    expect(sharedBidNote([bid(81), bid(60)])).toBeNull();
    expect(sharedBidNote([bid(81), { faab: null }])).toBeNull();
    expect(sharedBidNote([bid(81), { faab: { applicable: false } }])).toBeNull();
  });
});
