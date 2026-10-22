import { describe, expect, it } from "vitest";

import {
  SHEET_FLICK_MIN_DISTANCE_PX,
  classifySheetGesture,
  rubberBand,
  sheetDismissDistance,
  sheetDragOffset,
  shouldDismissSheet,
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
