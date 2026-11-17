import { describe, expect, it } from "vitest";

import { decideSwipe, lockSwipeAxis, swipeMayStart, swipeProgress, swipeTargetKey } from "./swipeTabs";

const start = { startX: 200, viewportWidth: 390, inHorizontalScroller: false, edgeGuard: 20 };

describe("swipeMayStart", () => {
  it("allows a mid-screen touch", () => expect(swipeMayStart(start)).toBe(true));
  it("ignores touches in a horizontal scroller", () => expect(swipeMayStart({ ...start, inHorizontalScroller: true })).toBe(false));
  it("ignores both screen edges when guarded", () => {
    expect(swipeMayStart({ ...start, startX: 8 })).toBe(false);
    expect(swipeMayStart({ ...start, startX: 385 })).toBe(false);
  });
  it("has no edge guard when set to 0 (mobile)", () => expect(swipeMayStart({ ...start, startX: 4, edgeGuard: 0 })).toBe(true));
});

describe("lockSwipeAxis", () => {
  it("stays undecided inside the slop", () => expect(lockSwipeAxis(6, 4)).toBe("undecided"));
  it("locks clearly horizontal", () => expect(lockSwipeAxis(-40, 10)).toBe("horizontal"));
  it("locks vertical", () => expect(lockSwipeAxis(8, 30)).toBe("vertical"));
  it("a diagonal is not horizontal", () => expect(lockSwipeAxis(30, 25)).toBe("undecided"));
});

describe("decideSwipe", () => {
  it("left swipe goes next", () => expect(decideSwipe(-80, 5, 0, true, true)).toBe("next"));
  it("right swipe goes prev", () => expect(decideSwipe(80, 5, 0, true, true)).toBe("prev"));
  it("short slow drag does nothing", () => expect(decideSwipe(-30, 2, 0.1, true, true)).toBe("none"));
  it("a flick commits on a short travel", () => expect(decideSwipe(-30, 2, -0.8, true, true)).toBe("next"));
  it("vertical-ish never swipes", () => expect(decideSwipe(-80, 70, -1, true, true)).toBe("none"));
  it("no neighbour means none", () => {
    expect(decideSwipe(-80, 0, 0, true, false)).toBe("none");
    expect(decideSwipe(80, 0, 0, false, true)).toBe("none");
  });
});

describe("swipeProgress", () => {
  it("is dx over width, clamped", () => {
    expect(swipeProgress(-195, 390, true, true)).toBeCloseTo(-0.5);
    expect(swipeProgress(-900, 390, true, true)).toBe(-1);
  });
  it("rubber-bands with no neighbour", () => expect(swipeProgress(-390, 390, true, false)).toBeCloseTo(-1 / 3));
  it("handles zero width", () => expect(swipeProgress(10, 0, true, true)).toBe(0));
});

describe("swipeTargetKey", () => {
  const keys = ["a", "b", "c"];
  it("moves along", () => {
    expect(swipeTargetKey(keys, "b", "next")).toBe("c");
    expect(swipeTargetKey(keys, "b", "prev")).toBe("a");
  });
  it("stays at the ends and on none", () => {
    expect(swipeTargetKey(keys, "c", "next")).toBe("c");
    expect(swipeTargetKey(keys, "a", "prev")).toBe("a");
    expect(swipeTargetKey(keys, "b", "none")).toBe("b");
  });
});
