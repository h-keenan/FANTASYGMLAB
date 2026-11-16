import { describe, expect, it } from "vitest";

import { simDraftNeedLabel, simDraftNeedPills, simDraftRosterStrip } from "./simDraft";
import type { SimGamePlayer, SimSlot } from "./simGame";

const p = (id: string, pos: SimGamePlayer["pos"]): SimGamePlayer => ({ id, name: id, pos }) as SimGamePlayer;
const slots = ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "K"] as SimSlot[];

describe("simDraftRosterStrip", () => {
  it("lists the slots in order, fills strict slots first, then flex, then bench", () => {
    const roster = [p("rb1", "RB"), p("rb2", "RB"), p("rb3", "RB"), p("wr1", "WR"), p("qb2", "QB")];
    const s = simDraftRosterStrip(roster, slots, 15);
    expect(s.slots.map((c) => c.label)).toEqual(["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "K"]);
    expect(s.slots.map((c) => c.player?.id ?? null)).toEqual(["qb2", "rb1", "rb2", "wr1", null, null, "rb3", null]);
    expect(s.bench).toEqual({ have: 0, max: 7 });
    expect(s.empty).toBe(3);
  });
  it("tints only strict empty slots as needs, matching the header need label", () => {
    const roster = [p("rb1", "RB"), p("wr1", "WR"), p("wr2", "WR")];
    const s = simDraftRosterStrip(roster, slots, 15);
    const needSlots = s.slots.filter((c) => c.need).map((c) => c.slot);
    expect(needSlots).toEqual(["QB", "RB", "TE", "K"]);
    const label = simDraftNeedLabel(simDraftNeedPills(roster, slots), 9) ?? "";
    for (const pos of needSlots) expect(label).toContain(pos);
    expect(s.slots.find((c) => c.slot === "FLEX")?.need).toBe(false);
  });
  it("counts extra players as bench with the league bench size", () => {
    const roster = [p("a", "QB"), p("b", "QB"), p("c", "QB")];
    const s = simDraftRosterStrip(roster, slots, 15, 6);
    expect(s.bench).toEqual({ have: 2, max: 6 });
  });
  it("groups the full roster by position", () => {
    const s = simDraftRosterStrip([p("a", "RB"), p("b", "RB")], slots, 15);
    expect(s.groups.find((g) => g.pos === "RB")).toMatchObject({ have: 2, starters: 2 });
    expect(s.groups.find((g) => g.pos === "QB")).toMatchObject({ have: 0, starters: 1 });
  });
  it("handles an empty roster and superflex", () => {
    const sf = ["QB", "SUPER_FLEX"] as SimSlot[];
    const s = simDraftRosterStrip([], sf, 10);
    expect(s.empty).toBe(2);
    expect(s.slots[1].label).toBe("SF");
    expect(simDraftRosterStrip([p("q1", "QB"), p("q2", "QB")], sf, 10).slots[1].player?.id).toBe("q2");
  });
});
