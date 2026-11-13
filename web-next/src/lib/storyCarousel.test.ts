import { describe, expect, it } from "vitest";

import { storyInitial, storyIsLast, storyKeyAction, storyReducer, storySegmentFill, storySwipeAction, storyTapAction } from "./storyCarousel";

describe("storyCarousel", () => {
  it("moves one page at a time and clamps at both ends", () => {
    let s = storyInitial(3);
    expect(s).toEqual({ index: 0, count: 3, direction: "none" });
    s = storyReducer(s, { type: "prev" });
    expect(s.index).toBe(0);
    s = storyReducer(storyReducer(s, { type: "next" }), { type: "next" });
    expect(s).toMatchObject({ index: 2, direction: "next" });
    expect(storyIsLast(s)).toBe(true);
    expect(storyReducer(s, { type: "next" })).toBe(s);
    expect(storyReducer(s, { type: "prev" })).toMatchObject({ index: 1, direction: "prev" });
  });
  it("goto clamps and reports the direction; a shrinking page count keeps the index valid", () => {
    let s = storyInitial(5, 9);
    expect(s.index).toBe(4);
    s = storyReducer(s, { type: "goto", index: 1 });
    expect(s).toMatchObject({ index: 1, direction: "prev" });
    s = storyReducer(storyReducer(s, { type: "goto", index: 4 }), { type: "count", count: 3 });
    expect(s.index).toBe(2);
    expect(storyInitial(0).index).toBe(0);
  });
  it("tap zones: left 30% goes back, the rest forward", () => {
    expect(storyTapAction(10, 390)).toBe("prev");
    expect(storyTapAction(116, 390)).toBe("prev");
    expect(storyTapAction(120, 390)).toBe("next");
    expect(storyTapAction(380, 390)).toBe("next");
    expect(storyTapAction(5, 0)).toBe("next");
  });
  it("swipes need distance and a mostly horizontal path", () => {
    expect(storySwipeAction(-80, 5)).toBe("next");
    expect(storySwipeAction(80, -5)).toBe("prev");
    expect(storySwipeAction(-30, 0)).toBeNull();
    expect(storySwipeAction(-80, 70)).toBeNull();
  });
  it("keys and progress segments", () => {
    expect(storyKeyAction("ArrowRight")).toBe("next");
    expect(storyKeyAction("ArrowLeft")).toBe("prev");
    expect(storyKeyAction("Escape")).toBe("close");
    expect(storyKeyAction("a")).toBeNull();
    expect([0, 1, 2, 3].map((i) => storySegmentFill(i, 1))).toEqual([1, 1, 0, 0]);
  });
});
