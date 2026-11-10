import { describe, expect, it } from "vitest";

import type { RoundupSwap } from "./api";
import { formatPoints, predictabilityColorVar, regretBarPercent, roundupReasonMessage, roundupWeeks, swapLine } from "./roundupPresentation";

const swap = {
  slot: "RB",
  started: { player_id: "1", name: "Alpha", position: "RB", team: "X", points: 3 },
  benched: { player_id: "2", name: "Beta", position: "RB", team: "Y", points: 21.04 },
} as RoundupSwap;

describe("roundup presentation", () => {
  it("formats points and swap lines", () => {
    expect(formatPoints(3)).toBe("3.0");
    expect(formatPoints(null)).toBe("0.0");
    expect(swapLine(swap)).toBe("Alpha (3.0) over Beta (21.0)");
  });

  it("gives each predictability tag its own semantic color", () => {
    const colors = (["foreseeable", "coin_flip", "unforeseeable"] as const).map(predictabilityColorVar);
    expect(new Set(colors).size).toBe(3);
  });

  it("degrades every reason to specific copy, with a generic fallback", () => {
    expect(roundupReasonMessage("no_completed_week").title).toBe("No roundup yet");
    expect(roundupReasonMessage("unsupported_platform").subtitle).toContain("ESPN");
    expect(roundupReasonMessage("mystery").title).toBe("Roundup is not ready");
  });

  it("builds week lists and regret bars", () => {
    expect(roundupWeeks(3)).toEqual([1, 2, 3]);
    expect(roundupWeeks(0)).toEqual([]);
    expect(regretBarPercent(10, 20)).toBe(50);
    expect(regretBarPercent(0, 20)).toBe(0);
    expect(regretBarPercent(0.1, 100)).toBe(4);
  });
});
