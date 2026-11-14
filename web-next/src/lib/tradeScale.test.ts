import { describe, expect, it } from "vitest";

import type { SimGamePlayer } from "./simGame";
import { simAcceptanceMeter, simScaleAsset, tradeScaleCount, tradeScaleMissing, tradeScalePhase } from "./tradeScale";

describe("trade scale model", () => {
  it("walks empty, building, review, tweak", () => {
    expect(tradeScalePhase({ giveCount: 0, getCount: 0, tweaking: false })).toBe("empty");
    expect(tradeScalePhase({ giveCount: 1, getCount: 0, tweaking: false })).toBe("building");
    expect(tradeScalePhase({ giveCount: 0, getCount: 2, tweaking: true })).toBe("building");
    expect(tradeScalePhase({ giveCount: 1, getCount: 1, tweaking: false })).toBe("review");
    expect(tradeScalePhase({ giveCount: 1, getCount: 1, tweaking: true })).toBe("tweak");
  });

  it("says what is missing, and nothing once both sides are filled", () => {
    expect(tradeScaleMissing(0, 0)).toMatch(/what you send/);
    expect(tradeScaleMissing(0, 1)).toBe("Add something you send");
    expect(tradeScaleMissing(1, 0)).toBe("Add something you get");
    expect(tradeScaleMissing(1, 1)).toBeNull();
  });

  it("counts with the per-side cap", () => {
    expect(tradeScaleCount(2)).toBe("2");
    expect(tradeScaleCount(2, 6)).toBe("2 of 6");
  });

  it("the sim meter is three coarse plain-word steps with no number", () => {
    const steps = [simAcceptanceMeter("decline"), simAcceptanceMeter("counter"), simAcceptanceMeter("accept"), simAcceptanceMeter(null)];
    expect(steps.map((s) => s.label)).toEqual(["They would decline", "They would counter", "They would accept", "Checking their answer"]);
    expect(steps[0].position).toBeLessThan(steps[1].position);
    expect(steps[1].position).toBeLessThan(steps[2].position);
    for (const s of steps) {
      expect(s.edge).toBe(0);
      expect(`${s.label} ${s.description}`).not.toMatch(/\d/);
    }
  });
});

describe("sim scale assets", () => {
  it("maps a player to avatar fields with a projection detail and no rating, and a pick to its label", () => {
    const player = { id: "123", name: "Ja'Marr Chase", pos: "WR", team: "CIN", age: 25, projection: 15.2, status: "healthy", grade: "A" } as unknown as SimGamePlayer;
    const a = simScaleAsset(player as never);
    expect(a.player).toMatchObject({ id: "123", name: "Ja'Marr Chase", position: "WR", headshotId: "123" });
    expect(a.detail).toBe("CIN \u00b7 15.2");
    expect(JSON.stringify(a)).not.toMatch(/overall|trade_value/);
    const pick = simScaleAsset({ id: "pick:2027:1:t1", season: 2027, round: 1, own: false, orig_team_name: "Rivals" } as never);
    expect(pick.pickLabel).toContain("Round 1");
    expect(pick.pickLabel).toContain("via Rivals");
    expect(pick.player).toBeUndefined();
  });
});
