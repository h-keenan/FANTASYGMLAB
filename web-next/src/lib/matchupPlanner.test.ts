import { describe, expect, it } from "vitest";

import type { MatchupResponse, MatchupWhatIfCandidate } from "./api";
import { applySwap, emptySlotsOf, plannerBase, sleeperLeagueUrl, slotIndexFor, winPercent } from "./matchupPlanner";

const player = (id: string, slot: string) => ({ player_id: id, slot, name: id }) as never;

function matchup(overrides: Record<string, unknown> = {}): MatchupResponse {
  return {
    ok: true,
    best_ball: false,
    my_team: {
      starters: [player("a", "QB"), player("b", "WR")],
      open_slots: ["FLEX"],
      real_starters: [player("c", "QB")],
      real_empty_slots: [],
      has_live_data: false,
    },
    ...overrides,
  } as unknown as MatchupResponse;
}

const cand = (id: string) => ({ player: { player_id: id }, selectable: true }) as unknown as MatchupWhatIfCandidate;

describe("matchupPlanner", () => {
  it("starts from the suggested lineup and keeps open slots", () => {
    const base = plannerBase(matchup(), "suggested")!;
    expect(base.slots).toEqual([
      { slot: "QB", player_id: "a" },
      { slot: "WR", player_id: "b" },
      { slot: "FLEX", player_id: null },
    ]);
    expect(emptySlotsOf(base.slots)).toEqual(["FLEX"]);
  });

  it("uses Sleeper's lineup only when it is posted", () => {
    expect(plannerBase(matchup(), "actual")!.slots[0].player_id).toBe("a");
    const live = matchup();
    (live.my_team as { has_live_data: boolean }).has_live_data = true;
    expect(plannerBase(live, "actual")!.slots).toEqual([{ slot: "QB", player_id: "c" }]);
  });

  it("is hidden for best ball", () => {
    expect(plannerBase(matchup({ best_ball: true }), "suggested")).toBeNull();
  });

  it("swaps a bench player in and trades places with a starter", () => {
    const slots = [
      { slot: "RB", player_id: "r1" },
      { slot: "FLEX", player_id: "w1" },
    ];
    expect(applySwap(slots, 0, cand("bench"))[0].player_id).toBe("bench");
    expect(applySwap(slots, 0, cand("w1"))).toEqual([
      { slot: "RB", player_id: "w1" },
      { slot: "FLEX", player_id: "r1" },
    ]);
  });

  it("finds lineup indexes for players and the n-th empty slot", () => {
    const slots = [
      { slot: "WR", player_id: "x" },
      { slot: "FLEX", player_id: null },
      { slot: "FLEX", player_id: null },
    ];
    expect(slotIndexFor(slots, player("x", "WR"), "WR", 0)).toBe(0);
    expect(slotIndexFor(slots, "empty", "FLEX", 1)).toBe(2);
  });

  it("formats win percent and the Sleeper link", () => {
    expect(winPercent({ available: true, probability: 0.644 })).toBe(64);
    expect(winPercent({ available: false })).toBeNull();
    expect(sleeperLeagueUrl("123")).toBe("https://sleeper.com/leagues/123");
  });
});
