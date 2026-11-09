import { describe, expect, it } from "vitest";

import type { DraftPickAsset } from "@/lib/api";
import { groupPicksForList, ordinal, pickProvenance, roundGroupDefaultOpen } from "./pickGroups";

function pick(season: number, round: number, extra: Partial<DraftPickAsset> = {}): DraftPickAsset {
  return {
    pick_id: `${season}:${round}:${extra.original_roster_id ?? "1"}`,
    label: `${season} ${round}`,
    score: 100,
    season,
    round,
    original_roster_id: "1",
    owner_roster_id: "1",
    ...extra,
  } as DraftPickAsset;
}

describe("pickGroups", () => {
  it("groups by season then round with counts, ascending", () => {
    const groups = groupPicksForList([pick(2028, 2), pick(2027, 2), pick(2027, 1), pick(2027, 2, { original_roster_id: "4" })]);
    expect(groups.map((g) => [g.label, g.count])).toEqual([["2027", 3], ["2028", 1]]);
    expect(groups[0].rounds.map((r) => [r.label, r.picks.length])).toEqual([["1st round", 1], ["2nd round", 2]]);
  });
  it("puts unknown season last as Future", () => {
    const groups = groupPicksForList([{ ...pick(0, 1), season: null } as unknown as DraftPickAsset, pick(2027, 1)]);
    expect(groups.map((g) => g.label)).toEqual(["2027", "Future"]);
  });
  it("ordinals", () => {
    expect([1, 2, 3, 4, 11, 12, 13, 21].map(ordinal)).toEqual(["1st", "2nd", "3rd", "4th", "11th", "12th", "13th", "21st"]);
  });
  it("provenance", () => {
    expect(pickProvenance(pick(2027, 1))).toBe("Own");
    expect(pickProvenance(pick(2027, 1, { original_roster_id: "2", original_team_name: "Team X" }))).toBe("From Team X");
    expect(pickProvenance(pick(2027, 1, { owner_team_name: "Me" }), { showOwner: true })).toBe("Me · Own");
  });
  it("default open rule", () => {
    const big = { round: 2, label: "2nd round", picks: [1, 2, 3, 4].map((i) => pick(2027, 2, { original_roster_id: String(i) })) };
    expect(roundGroupDefaultOpen(big, false)).toBe(false);
    expect(roundGroupDefaultOpen(big, true)).toBe(true);
    expect(roundGroupDefaultOpen(big, false, new Set([big.picks[2].pick_id]))).toBe(true);
  });
});
