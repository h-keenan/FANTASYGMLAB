import { describe, expect, it } from "vitest";

import { pillOrbBadge, simPillPlan, type PillContext } from "./bottomNav";

const ctx = (over: Partial<PillContext>): PillContext => ({ id: "x", label: "x", tabs: [], activeKey: "", onSelect: () => {}, ...over });
const auto = { key: "auto-set", label: "Auto-set", onPress: () => {} };
const tabs = [{ key: "a", label: "A" }, { key: "b", label: "B" }];

describe("simPillPlan (smart Fantasy Sim footer)", () => {
  it("plain in-season page: orb | Sim to | Advance", () => {
    expect(simPillPlan({ context: null, simToAvailable: true })).toEqual({ segment: null, inlineAction: null, simTo: true, advance: true });
  });
  it("a page action takes Sim to's slot and keeps Advance", () => {
    const p = simPillPlan({ context: ctx({ primary: auto }), simToAvailable: true });
    expect(p.inlineAction?.key).toBe("auto-set");
    expect(p.simTo).toBe(false);
    expect(p.advance).toBe(true);
  });
  it("a disabled page action does not apply: hidden, Sim to returns", () => {
    const p = simPillPlan({ context: ctx({ primary: { ...auto, disabled: true } }), simToAvailable: true });
    expect(p.inlineAction).toBeNull();
    expect(p.simTo).toBe(true);
    expect(simPillPlan({ context: ctx({ primary: { ...auto, disabled: true, busy: true } }), simToAvailable: true }).inlineAction).not.toBeNull();
  });
  it("tabs (the draft room) own the pill: no Advance, no Sim to", () => {
    const p = simPillPlan({ context: ctx({ tabs, activeKey: "a", primary: auto }), simToAvailable: true });
    expect(p.segment?.tabs).toHaveLength(2);
    expect(p).toMatchObject({ inlineAction: null, simTo: false, advance: false });
  });
  it("paywalled or offseason (no Sim to available): never Sim to", () => {
    expect(simPillPlan({ context: null, simToAvailable: true, paywalled: true }).simTo).toBe(false);
    expect(simPillPlan({ context: null, simToAvailable: false }).simTo).toBe(false);
  });
});

describe("pillOrbBadge", () => {
  it("sums the global tab counts", () => {
    expect(pillOrbBadge([{ badge: 2 }, { badge: 0 }, {}, { badge: 3 }])).toBe(5);
  });
});
