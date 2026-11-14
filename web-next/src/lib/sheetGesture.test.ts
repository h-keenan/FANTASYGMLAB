import { describe, expect, it } from "vitest";

import {
  SHEET_FLICK_MIN_DISTANCE_PX,
  canStartSheetDrag,
  classifySheetGesture,
  sheetDragProgress,
  rubberBand,
  sheetDismissDistance,
  sheetDragOffset,
  shouldDismissSheet,
  SHEET_DRAG_IDLE,
  resolveSheetRelease,
  sheetDragEnd,
  sheetDragMove,
  sheetDragPosition,
  sheetDragStart,
  sheetReleaseVelocity,
  sheetStops,
  type SheetDragState,
} from "./sheetGesture";

describe("sheetDismissDistance", () => {
  it("is a quarter of the sheet height, clamped to 80..160px", () => {
    expect(sheetDismissDistance(400)).toBe(100);
    expect(sheetDismissDistance(200)).toBe(80);
    expect(sheetDismissDistance(2000)).toBe(160);
    expect(sheetDismissDistance(0)).toBe(120);
  });
});

describe("shouldDismissSheet", () => {
  it("dismisses past the distance threshold even when released slowly", () => {
    expect(shouldDismissSheet({ offset: 101, velocity: 0, sheetHeight: 400 })).toBe(true);
    expect(shouldDismissSheet({ offset: 99, velocity: 0, sheetHeight: 400 })).toBe(false);
  });

  it("dismisses a fast downward flick that actually moved the sheet", () => {
    expect(shouldDismissSheet({ offset: 40, velocity: 0.8, sheetHeight: 800 })).toBe(true);
    expect(shouldDismissSheet({ offset: SHEET_FLICK_MIN_DISTANCE_PX - 1, velocity: 2, sheetHeight: 800 })).toBe(false);
    expect(shouldDismissSheet({ offset: 40, velocity: 0.3, sheetHeight: 800 })).toBe(false);
  });

  it("never dismisses when released moving back up, or at rest", () => {
    expect(shouldDismissSheet({ offset: 300, velocity: -0.2, sheetHeight: 400 })).toBe(false);
    expect(shouldDismissSheet({ offset: 0, velocity: 3, sheetHeight: 400 })).toBe(false);
    expect(shouldDismissSheet({ offset: -10, velocity: 3, sheetHeight: 400 })).toBe(false);
  });
});

describe("rubber band", () => {
  it("grows with distance but never past its dimension", () => {
    expect(rubberBand(0, 100)).toBe(0);
    const a = rubberBand(50, 100);
    const b = rubberBand(500, 100);
    expect(a).toBeGreaterThan(0);
    expect(b).toBeGreaterThan(a);
    expect(b).toBeLessThan(100);
    expect(rubberBand(50, 100)).toBeLessThan(50);
  });

  it("follows the finger 1:1 down to the threshold, then resists", () => {
    expect(sheetDragOffset(60, 400)).toBe(60);
    expect(sheetDragOffset(100, 400)).toBe(100);
    const past = sheetDragOffset(200, 400);
    expect(past).toBeGreaterThan(100);
    expect(past).toBeLessThan(200);
  });

  it("only stretches a little when pulled upward", () => {
    const up = sheetDragOffset(-200, 400);
    expect(up).toBeLessThan(0);
    expect(up).toBeGreaterThan(-40);
  });
});

describe("classifySheetGesture", () => {
  it("waits inside the slop", () => {
    expect(classifySheetGesture({ dx: 2, dy: 5, canStartDrag: true })).toBeNull();
  });

  it("drags on a mostly vertical downward pull when allowed to start", () => {
    expect(classifySheetGesture({ dx: 3, dy: 20, canStartDrag: true })).toBe("drag");
  });

  it("ignores a downward pull when the content under the finger is scrolled", () => {
    expect(classifySheetGesture({ dx: 0, dy: 20, canStartDrag: false })).toBe("ignore");
  });

  it("ignores upward and horizontal gestures", () => {
    expect(classifySheetGesture({ dx: 0, dy: -20, canStartDrag: true })).toBe("ignore");
    expect(classifySheetGesture({ dx: 30, dy: 12, canStartDrag: true })).toBe("ignore");
  });
});

describe("canStartSheetDrag", () => {
  it("always starts on the grab handle, even over scrolled content", () => {
    expect(canStartSheetDrag({ onHandle: true, scrollTops: [400] })).toBe(true);
  });
  it("starts from the header or top area (no scrolling ancestor) and from a body scrolled to its top", () => {
    expect(canStartSheetDrag({ onHandle: false, scrollTops: [] })).toBe(true);
    expect(canStartSheetDrag({ onHandle: false, scrollTops: [0, 0] })).toBe(true);
  });
  it("does not start from a body (or any nested scroller) scrolled away from the top", () => {
    expect(canStartSheetDrag({ onHandle: false, scrollTops: [0, 2] })).toBe(false);
    expect(canStartSheetDrag({ onHandle: false, scrollTops: [0.6] })).toBe(true);
    expect(canStartSheetDrag({ onHandle: false, scrollTops: [250] })).toBe(false);
  });
  it("a negative scrollTop (iOS overscroll bounce) still counts as the top", () => {
    expect(canStartSheetDrag({ onHandle: false, scrollTops: [-12] })).toBe(true);
  });
});

describe("sheetDragProgress", () => {
  it("is 0 at rest or pulled up, and rises to 1 as the sheet leaves", () => {
    expect(sheetDragProgress(0, 500)).toBe(0);
    expect(sheetDragProgress(-20, 500)).toBe(0);
    expect(sheetDragProgress(250, 500)).toBe(0.5);
    expect(sheetDragProgress(900, 500)).toBe(1);
    expect(sheetDragProgress(50, 0)).toBe(0);
  });
});

describe("dismiss decision at the documented thresholds", () => {
  it("dismisses past ~100px, or on a fast flick, and springs back otherwise", () => {
    expect(shouldDismissSheet({ offset: 120, velocity: 0, sheetHeight: 400 })).toBe(true);
    expect(shouldDismissSheet({ offset: 60, velocity: 0.1, sheetHeight: 400 })).toBe(false);
    expect(shouldDismissSheet({ offset: 40, velocity: 0.9, sheetHeight: 400 })).toBe(true);
    expect(shouldDismissSheet({ offset: 120, velocity: -0.4, sheetHeight: 400 })).toBe(false);
  });
});

// --- state machine: simulated touch sequences -------------------------------------------------------------------

type Pt = [x: number, y: number, t: number];

/** Runs a whole touch through the machine; returns the final state and what the release decided. */
function run(points: Pt[], opts: { onHandle?: boolean; scrollTops?: number[]; height?: number; stops?: number[]; stopIndex?: number } = {}) {
  const [first, ...rest] = points;
  let state: SheetDragState = sheetDragStart({
    x: first[0],
    y: first[1],
    t: first[2],
    onHandle: opts.onHandle ?? false,
    scrollTops: opts.scrollTops ?? [0],
    height: opts.height ?? 800,
    stops: opts.stops,
    stopIndex: opts.stopIndex,
  });
  for (const [x, y, t] of rest) state = sheetDragMove(state, { x, y, t });
  const last = points[points.length - 1];
  return { state, release: sheetDragEnd(state, last[2]) };
}

/** A steady drag: `steps` samples 16ms apart moving `dy` px in total. */
function steady(dy: number, steps: number, dx = 0, startY = 100): Pt[] {
  const pts: Pt[] = [[100, startY, 0]];
  for (let i = 1; i <= steps; i += 1) pts.push([100 + (dx * i) / steps, startY + (dy * i) / steps, i * 16]);
  return pts;
}

describe("sheetReleaseVelocity", () => {
  it("averages over the trailing window instead of the last two samples", () => {
    // One 2px jitter 1ms apart is not a 2px/ms flick.
    const samples = [
      { y: 100, t: 0 },
      { y: 110, t: 40 },
      { y: 120, t: 80 },
      { y: 122, t: 81 },
    ];
    expect(sheetReleaseVelocity(samples, 82)).toBeCloseTo(22 / 81, 2);
  });
  it("is 0 for a lone sample or a finger that rested before lifting", () => {
    expect(sheetReleaseVelocity([{ y: 1, t: 0 }], 10)).toBe(0);
    expect(sheetReleaseVelocity([{ y: 0, t: 0 }, { y: 80, t: 20 }], 400)).toBe(0);
  });
});

describe("gesture state machine: dismiss decision", () => {
  it("a slow short drag snaps back", () => {
    const { release } = run(steady(60, 30)); // 60px over ~480ms
    expect(release).toEqual({ type: "snap", index: 0 });
  });

  it("a slow drag past the distance threshold dismisses", () => {
    const { release } = run(steady(200, 50)); // 200px (past 160 on an 800px sheet), ~0.2px/ms
    expect(release).toEqual({ type: "dismiss" });
  });

  it("a fast flick dismisses even when short", () => {
    const { release } = run(steady(70, 4)); // 70px in 64ms ~ 1.1px/ms
    expect(release).toEqual({ type: "dismiss" });
  });

  it("a fast twitch of a few pixels never dismisses", () => {
    const { release } = run([[100, 100, 0], [100, 112, 8], [100, 120, 16]]);
    expect(release).toEqual({ type: "snap", index: 0 });
  });

  it("a single jittery last sample does not turn a slow drag into a flick", () => {
    const pts = steady(50, 25);
    pts.push([100, 152, pts[pts.length - 1][2] + 1]);
    expect(run(pts).release).toEqual({ type: "snap", index: 0 });
  });

  it("reversing direction before release cancels: pulled down then flicked back up never dismisses", () => {
    const pts: Pt[] = [[100, 100, 0], [100, 150, 40], [100, 230, 80], [100, 200, 100], [100, 150, 120]];
    expect(run(pts).release).toEqual({ type: "snap", index: 0 });
  });

  it("holding still before lifting is not a flick", () => {
    const pts: Pt[] = [[100, 100, 0], [100, 130, 16], [100, 150, 32]];
    const state = run(pts).state;
    expect(sheetDragEnd(state, 600)).toEqual({ type: "snap", index: 0 });
  });
});

describe("gesture state machine: start-zone rules", () => {
  it("content at scrollTop 0 starts a downward drag", () => {
    expect(run(steady(30, 6), { scrollTops: [0] }).state.phase).toBe("drag");
    expect(run(steady(30, 6), { scrollTops: [] }).state.phase).toBe("drag");
  });

  it("a drag inside scrolled content never dismisses (even a huge fast pull)", () => {
    const { state, release } = run(steady(400, 4), { scrollTops: [300] });
    expect(state.phase).toBe("ignored");
    expect(release).toBeNull();
  });

  it("a nested scroller that is not at its top blocks the drag too", () => {
    expect(run(steady(60, 6), { scrollTops: [0, 40] }).release).toBeNull();
  });

  it("the handle always drags, over scrolled content", () => {
    expect(run(steady(160, 10), { onHandle: true, scrollTops: [500] }).release).toEqual({ type: "dismiss" });
  });

  it("an upward pull at a full sheet is a scroll, not a drag", () => {
    const { state, release } = run(steady(-80, 8));
    expect(state.phase).toBe("ignored");
    expect(release).toBeNull();
  });
});

describe("gesture state machine: axis lock", () => {
  it("a horizontal swipe (tab strip) is never a drag", () => {
    const { state, release } = run(steady(5, 8, 160));
    expect(state.phase).toBe("ignored");
    expect(release).toBeNull();
  });

  it("a sideways swipe that drifts down is still the tab strip's", () => {
    const { release } = run(steady(70, 8, 120));
    expect(release).toBeNull();
  });

  it("a diagonal that never resolves goes back to the page", () => {
    const { state } = run([[100, 100, 0], [120, 124, 16], [140, 148, 32]]);
    expect(state.phase).toBe("ignored");
  });

  it("a clear vertical pull with slight sideways wobble still drags", () => {
    expect(run(steady(100, 10, 12)).state.phase).toBe("drag");
  });

  it("waits inside the slop (a tap never moves the sheet)", () => {
    const { state, release } = run([[100, 100, 0], [102, 105, 30]]);
    expect(state.phase).toBe("pending");
    expect(release).toBeNull();
  });

  it("does not jump by the slop when the drag is claimed", () => {
    const { state } = run([[100, 100, 0], [100, 112, 16]]);
    expect(state.phase).toBe("drag");
    expect(state.position).toBe(0);
  });
});

describe("sheetStops / snap points", () => {
  it("turns visible fractions into resting offsets, top first", () => {
    expect(sheetStops([0.5, 1], 800)).toEqual([0, 400]);
    expect(sheetStops(undefined, 800)).toEqual([0]);
    expect(sheetStops([1], 0)).toEqual([0]);
  });

  const stops = [0, 400];
  it("a slow drag from the peek past halfway toward full settles on full", () => {
    const { release } = run(steady(-250, 30, 0, 500), { stops, stopIndex: 1 });
    expect(release).toEqual({ type: "snap", index: 0 });
  });

  it("a short slow drag up from the peek springs back to the peek", () => {
    const { release } = run(steady(-60, 30, 0, 500), { stops, stopIndex: 1 });
    expect(release).toEqual({ type: "snap", index: 1 });
  });

  it("an upward flick from the peek goes to full", () => {
    expect(run(steady(-60, 4, 0, 500), { stops, stopIndex: 1 }).release).toEqual({ type: "snap", index: 0 });
  });

  it("an upward pull from content works at the peek (content is not scrollable until full)", () => {
    expect(run(steady(-60, 4, 0, 500), { stops, stopIndex: 1, scrollTops: [0] }).state.phase).toBe("drag");
  });

  it("a downward flick from full lands on the peek, not dismissed", () => {
    expect(run(steady(80, 4), { stops, stopIndex: 0 }).release).toEqual({ type: "snap", index: 1 });
  });

  it("a downward drag from the peek past the distance dismisses; a short one springs back", () => {
    expect(run(steady(160, 30, 0, 500), { stops, stopIndex: 1 }).release).toEqual({ type: "dismiss" });
    expect(run(steady(40, 30, 0, 500), { stops, stopIndex: 1 }).release).toEqual({ type: "snap", index: 1 });
  });

  it("a downward flick from the peek dismisses", () => {
    expect(run(steady(80, 4, 0, 500), { stops, stopIndex: 1 }).release).toEqual({ type: "dismiss" });
  });

  it("drag position is continuous across stops and resists past the top", () => {
    expect(sheetDragPosition({ base: 400, delta: -200, stops, height: 800 })).toBe(200);
    const above = sheetDragPosition({ base: 400, delta: -600, stops, height: 800 });
    expect(above).toBeLessThan(0);
    expect(above).toBeGreaterThan(-40);
  });

  it("a sheet that cannot be dismissed resists immediately below its lowest stop", () => {
    expect(sheetDragPosition({ base: 0, delta: 60, stops: [0], height: 800, dismissible: false })).toBeLessThan(60);
    expect(resolveSheetRelease({ position: 300, velocity: 2, height: 800, stops: [0], dismissible: false })).toEqual({ type: "snap", index: 0 });
  });
});

describe("idle state", () => {
  it("ignores moves and never releases", () => {
    expect(sheetDragMove(SHEET_DRAG_IDLE, { x: 0, y: 50, t: 1 })).toBe(SHEET_DRAG_IDLE);
    expect(sheetDragEnd(SHEET_DRAG_IDLE, 10)).toBeNull();
  });
});
