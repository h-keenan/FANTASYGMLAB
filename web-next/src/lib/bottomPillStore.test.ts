import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getPillState, PILL_CLEAR_DELAY_MS, resetPillStore, setPillBarPresent, setPillContext, subscribePill } from "./bottomPillStore";

const ctx = (over = {}) => ({ id: "team", label: "Team", tabs: [{ key: "a", label: "A" }], activeKey: "a", onSelect: () => {}, ...over });

describe("bottomPillStore", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    resetPillStore();
  });
  afterEach(() => vi.useRealTimers());
  it("a page swap (unmount then mount) never shows the plain global pill in between", () => {
    const a = {};
    const b = {};
    setPillContext(a, ctx());
    setPillContext(a, null);
    setPillContext(b, ctx({ activeKey: "a" }));
    vi.advanceTimersByTime(PILL_CLEAR_DELAY_MS + 1);
    expect(getPillState().ctx?.id).toBe("team");
  });

  it("publishes only when what is shown changes, and keeps callbacks fresh", () => {
    const l = vi.fn();
    subscribePill(l);
    const who = {};
    const first = vi.fn();
    const second = vi.fn();
    setPillContext(who, ctx({ onSelect: first }));
    setPillContext(who, ctx({ onSelect: second }));
    expect(l).toHaveBeenCalledTimes(1);
    getPillState().ctx?.onSelect("a");
    expect(first).not.toHaveBeenCalled();
    expect(second).toHaveBeenCalledWith("a");
    setPillContext(who, ctx({ activeKey: "zzz", tabs: [{ key: "a", label: "A" }, { key: "b", label: "B" }] }));
    expect(l).toHaveBeenCalledTimes(2);
  });
  it("only the owner may clear, and the bar-present flag is tracked", () => {
    const a = {};
    const b = {};
    setPillContext(a, ctx());
    setPillContext(b, ctx({ id: "trades" }));
    setPillContext(a, null);
    expect(getPillState().ctx?.id).toBe("trades");
    setPillContext(b, null);
    vi.advanceTimersByTime(PILL_CLEAR_DELAY_MS + 1);
    expect(getPillState().ctx).toBeNull();
    setPillBarPresent(true);
    expect(getPillState().barPresent).toBe(true);
  });
});
