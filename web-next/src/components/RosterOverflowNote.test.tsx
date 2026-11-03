import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { RosterOverflowNote } from "./SuggestedDrop";
import type { DropPlayer, RosterOverflow } from "@/lib/api";

const effect = { lineup_points_ros: 0, lineup_points_per_week: 0, this_week: 0, value_delta: -4228, score: -4228, weeks: 9 };

function cut(id: string, name: string): DropPlayer {
  return {
    player_id: id, name, position: "WR", team: "NYJ", age: 29, status: "Active", injury_status: "", value: 900,
    start_share: 0, usage_flag: null, reasons: ["never starts in your best lineup"], effect, action: "drop",
  };
}

const OVERFLOW: RosterOverflow = {
  need: 2,
  drops: [cut("a", "Justin Fields"), cut("b", "Sean Tucker")],
  satisfied: true,
  effect,
  roster: { active_limit: 22, active_count: 22, open_spots: 0, is_full: true, reserve_slots: 4, reserve_used: 4, taxi_slots: 5, taxi_used: 4 },
  active_after: 24,
  active_limit: 22,
};

describe("RosterOverflowNote", () => {
  it("says you'd have to drop N, names them, and states the cost already in the result", () => {
    render(<RosterOverflowNote overflow={OVERFLOW} />);
    const note = screen.getByTestId("roster-overflow");
    expect(note).toHaveTextContent("you'd have to drop 2 players: Justin Fields, Sean Tucker");
    expect(note).toHaveTextContent("24/22");
    expect(note).toHaveTextContent("Cost of the cuts, already in this result: No lineup change · Value -4,228");
  });

  it("is honest when no safe cut exists or the cuts cannot be named", () => {
    const { rerender } = render(<RosterOverflowNote overflow={{ ...OVERFLOW, satisfied: false, drops: [] }} />);
    expect(screen.getByTestId("roster-overflow")).toHaveTextContent(/not enough safe cuts/);
    rerender(<RosterOverflowNote overflow={{ ...OVERFLOW, unavailable: "untouchable_lookup_failed", drops: [], satisfied: false, effect: null }} />);
    expect(screen.getByTestId("roster-overflow")).toHaveTextContent(/could not be named safely/);
  });
});
