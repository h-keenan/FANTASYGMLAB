import { describe, expect, it } from "vitest";

import { compactSummaryText } from "./compactModule";
import { offseasonAgingParts, offseasonClockParts, offseasonPositionMix, offseasonReserveParts, offseasonRetireParts, offseasonRosterParts, offseasonStepper } from "./simOffseasonSummary";

describe("simOffseasonSummary", () => {
  it("stepper carries an icon, a one-word label and a spoken state per step", () => {
    const s = offseasonStepper([
      { key: "review", label: "Review", state: "done" },
      { key: "rookie_draft", label: "Rookie draft", state: "current" },
      { key: "cutdown", label: "Roster check", state: "todo" },
    ]);
    expect(s.map((x) => x.short)).toEqual(["Review", "Draft", "Roster"]);
    expect(s[1].aria).toBe("Rookie draft, current step");
    expect(s.every((x) => x.icon)).toBe(true);
  });
  it("module summaries are dense lines, never empty", () => {
    expect(compactSummaryText(offseasonRetireParts([{ is_yours: true }, { is_yours: false }]) as never)).toBe("2 retired · 1 yours");
    expect(compactSummaryText(offseasonAgingParts([{ delta: 1 }, { delta: -1 }, { delta: 0 }]) as never)).toBe("1 up · 1 down");
    expect(compactSummaryText(offseasonClockParts({ on_clock: { round: 2, n: 5, team_name: "Bench Mob" } as never, your_turn: true, total: 48, pick_index: 4, available_count: 38 }) as never)).toBe("R2 P5 · You pick now · 38 left");
    expect(offseasonPositionMix([{ pos: "WR" }, { pos: "QB" }, { pos: "WR" }])).toBe("QB1 WR2");
    expect(compactSummaryText(offseasonRosterParts({ size: 14, limit: 12, cuts_needed: 2 }, [{ pos: "QB" }]) as never)).toBe("14/12 spots · cut 2 · QB1");
    expect(compactSummaryText(offseasonReserveParts({ enabled: true, ir_slots: 2, taxi_slots: 4, taxi_years: 2, ir_used: 1, taxi_used: 0 }) as never)).toBe("IR 1/2 · Taxi 0/4");
  });
});
