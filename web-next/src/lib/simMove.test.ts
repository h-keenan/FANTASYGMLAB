import { describe, expect, it } from "vitest";

import { simHasMove, simMoveSpecs } from "./simMove";
import type { SimGamePlayer } from "./simGame";

const p = (over: Partial<SimGamePlayer> = {}) => ({ id: "p1", name: "Pat Nacua", pos: "WR", squad: "roster", status: "healthy", out_weeks: 0, taxi_eligible: false, ...over }) as unknown as SimGamePlayer;
const reserve = (over = {}) => ({ reserves: { enabled: true, ir_slots: 2, ir_used: 0, taxi_slots: 2, taxi_used: 0 }, rosterSize: 10, rosterLimit: 18, ...over }) as never;

describe("simMoveSpecs", () => {
  it("lists only what is possible: a healthy non-rookie bench WR gets swap, block, profile and cut", () => {
    const specs = simMoveSpecs({ player: p(), reserve: reserve(), swapTargets: [{ index: 2, label: "WR2", current: p({ id: "p2", name: "Jo Smith" }) }], block: { on: false }, profile: true, canCut: true });
    expect(specs.map((s) => s.kind)).toEqual(["swap", "block", "profile", "cut"]);
    expect(specs[0].targets?.[0]).toMatchObject({ label: "WR2", hint: "for Smith" });
  });

  it("an injured player also gets To IR; the first move action is the only primary", () => {
    const specs = simMoveSpecs({ player: p({ status: "out", out_weeks: 3 }), reserve: reserve(), swapTargets: [{ index: 0, label: "WR1", current: null }], canCut: true });
    expect(specs.map((s) => s.kind)).toEqual(["swap", "ir", "cut"]);
    expect(specs.filter((s) => s.primary)).toHaveLength(1);
    expect(specs[0].primary).toBe(true);
  });

  it("a locked lineup hides swap; no fitting slot hides swap; a starter gets one Change action", () => {
    expect(simMoveSpecs({ player: p(), swapTargets: [{ index: 0, label: "WR1", current: null }], lineupLocked: true }).map((s) => s.kind)).toEqual([]);
    expect(simMoveSpecs({ player: p(), swapTargets: [] }).map((s) => s.kind)).toEqual([]);
    const starter = simMoveSpecs({ player: p(), changeSlot: "WR1", canCut: true });
    expect(starter.map((s) => s.label)).toEqual(["Change WR1", "Cut"]);
  });

  it("an IR player can be activated (primary) and cut; a full roster hides Activate", () => {
    const ir = p({ squad: "ir" as never });
    expect(simMoveSpecs({ player: ir, reserve: reserve(), canCut: true }).map((s) => s.label)).toEqual(["Activate", "Cut"]);
    expect(simMoveSpecs({ player: ir, reserve: reserve({ rosterSize: 18 }), canCut: true }).map((s) => s.kind)).toEqual(["cut"]);
  });

  it("a full taxi squad offers swapping onto it", () => {
    const taxiPlayer = p({ id: "t1", name: "Rook One", squad: "taxi" as never });
    const specs = simMoveSpecs({ player: p({ taxi_eligible: true }), reserve: reserve({ reserves: { enabled: true, ir_slots: 2, ir_used: 0, taxi_slots: 1, taxi_used: 1 } }), taxi: [taxiPlayer] });
    expect(specs.map((s) => s.kind)).toEqual(["taxi_swap"]);
    expect(specs[0].targets?.[0].key).toBe("t1");
  });

  it("cut asks first, and Move is only needed when there is more than the profile", () => {
    const specs = simMoveSpecs({ player: p(), canCut: true, profile: true });
    expect(specs.find((s) => s.kind === "cut")?.confirm).toBe("Cut Nacua?");
    expect(simHasMove(simMoveSpecs({ player: p(), profile: true }))).toBe(false);
    expect(simHasMove(specs)).toBe(true);
  });
});
