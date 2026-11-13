import { describe, expect, it } from "vitest";

import { changedPlayerIds, compareLineupSlots, numberedSlotLabels, slotTotals, sortSlots } from "./lineupSlots";
import type { LineupComparisonRow, LineupPlayer } from "./matchupPresentation";

function player(
  id: string,
  slot: string,
  extra: Record<string, unknown> = {},
): LineupPlayer {
  return {
    player_id: id,
    name: `P${id}`,
    position: slot,
    team: "NYG",
    slot,
    injury_label: "",
    tier: null,
    projection: { status: "ok", point_estimate: 10, low: null, high: null, confidence: null, opponent: "DAL" },
    actual_points: null,
    game_started: false,
    game_status: "scheduled",
    ...extra,
  } as unknown as LineupPlayer;
}

const liveStarter = (id: string, slot: string, pts: number, projFinal: number) =>
  player(id, slot, { game_started: true, game_status: "in_progress", actual_points: pts, projected_final: projFinal, game_progress: 0.5 });
const finalStarter = (id: string, slot: string, pts: number) =>
  player(id, slot, { game_started: true, game_status: "final", game_final: true, actual_points: pts });

describe("lineup slot comparison", () => {
  it("numbers repeated slots only", () => {
    expect(numberedSlotLabels(["QB", "RB", "RB", "FLEX", "WR"])).toEqual(["QB", "RB1", "RB2", "FLEX", "WR"]);
  });

  it("finds the leader per slot and the mini-bar share", () => {
    const rows: LineupComparisonRow[] = [
      { slot: "QB", mine: finalStarter("1", "QB", 22), opponent: finalStarter("2", "QB", 15) },
      { slot: "RB", mine: liveStarter("3", "RB", 4, 9), opponent: liveStarter("4", "RB", 8, 16) },
      { slot: "WR", mine: player("5", "WR"), opponent: player("6", "WR") },
    ];
    const slots = compareLineupSlots(rows);
    expect(slots.map((slot) => slot.leader)).toEqual(["mine", "opponent", "tie"]);
    expect(slots[0].barShare).toBeCloseTo((22 / 37) * 100);
    expect(slots[2].barShare).toBe(50);
  });

  it("flags the closest still-open slots as deciding and ignores settled ones", () => {
    const rows: LineupComparisonRow[] = [
      { slot: "QB", mine: finalStarter("1", "QB", 22), opponent: finalStarter("2", "QB", 21) }, // closest but settled
      { slot: "RB", mine: liveStarter("3", "RB", 8, 15), opponent: liveStarter("4", "RB", 7, 14.5) },
      { slot: "WR", mine: player("5", "WR", { projection: { status: "ok", point_estimate: 11 } }), opponent: player("6", "WR", { projection: { status: "ok", point_estimate: 10.5 } }) },
      { slot: "TE", mine: player("7", "TE", { projection: { status: "ok", point_estimate: 20 } }), opponent: player("8", "TE", { projection: { status: "ok", point_estimate: 4 } }) },
    ];
    const slots = compareLineupSlots(rows);
    expect(slots.filter((slot) => slot.decides).map((slot) => slot.slot)).toEqual(["RB", "WR"]);
    expect(slots[0].decides).toBe(false);
    const sorted = sortSlots(slots, "decisive");
    expect(sorted.slice(0, 2).map((slot) => slot.slot)).toEqual(["RB", "WR"]);
    expect(sortSlots(slots, "lineup")).toBe(slots);
  });

  it("marks bye and out players unavailable and counts a bye as zero", () => {
    const rows: LineupComparisonRow[] = [
      { slot: "WR", mine: player("1", "WR", { projection: { status: "bye_week", point_estimate: null } }), opponent: player("2", "WR", { injury_label: "Out" }) },
    ];
    const [slot] = compareLineupSlots(rows);
    expect(slot.mineUnavailable).toBe(true);
    expect(slot.opponentUnavailable).toBe(true);
    expect(slot.myNow).toBe(0);
  });

  it("totals current and projected final", () => {
    const rows: LineupComparisonRow[] = [
      { slot: "QB", mine: finalStarter("1", "QB", 20), opponent: liveStarter("2", "QB", 10, 22) },
      { slot: "K", mine: "empty", opponent: null },
    ];
    const totals = slotTotals(compareLineupSlots(rows));
    expect(totals.mineNow).toBe(20);
    expect(totals.opponentNow).toBe(10);
    expect(totals.opponentFinal).toBe(22);
    expect(totals.marginFinal).toBe(-2);
  });

  it("reports players whose points changed between payloads", () => {
    const before = compareLineupSlots([{ slot: "RB", mine: liveStarter("3", "RB", 4, 9), opponent: liveStarter("4", "RB", 8, 16) }]);
    const after = compareLineupSlots([{ slot: "RB", mine: liveStarter("3", "RB", 10, 15), opponent: liveStarter("4", "RB", 8, 16) }]);
    expect([...changedPlayerIds(before, after)]).toEqual(["3"]);
    expect(changedPlayerIds(null, after).size).toBe(0);
  });
});
