// Run with: node --experimental-strip-types --test src/lib/sheetGesture.test.ts
// Same cases as web-next's sheetGesture.test.ts: both platforms share the rules.
import { describe, it } from 'node:test';
import assert from 'node:assert/strict';

import {
  SHEET_FLICK_MIN_DISTANCE_PX,
  classifySheetGesture,
  rubberBand,
  sheetDismissDistance,
  sheetDragOffset,
  shouldDismissSheet,
} from './sheetGesture.ts';

describe("sheetDismissDistance", () => {
  it("is a quarter of the sheet height, clamped to 80..160px", () => {
    assert.equal(sheetDismissDistance(400), 100);
    assert.equal(sheetDismissDistance(200), 80);
    assert.equal(sheetDismissDistance(2000), 160);
    assert.equal(sheetDismissDistance(0), 120);
  });
});

describe("shouldDismissSheet", () => {
  it("dismisses past the distance threshold even when released slowly", () => {
    assert.equal(shouldDismissSheet({ offset: 101, velocity: 0, sheetHeight: 400 }), true);
    assert.equal(shouldDismissSheet({ offset: 99, velocity: 0, sheetHeight: 400 }), false);
  });

  it("dismisses a fast downward flick that actually moved the sheet", () => {
    assert.equal(shouldDismissSheet({ offset: 40, velocity: 0.8, sheetHeight: 800 }), true);
    assert.equal(shouldDismissSheet({ offset: SHEET_FLICK_MIN_DISTANCE_PX - 1, velocity: 2, sheetHeight: 800 }), false);
    assert.equal(shouldDismissSheet({ offset: 40, velocity: 0.3, sheetHeight: 800 }), false);
  });

  it("never dismisses when released moving back up, or at rest", () => {
    assert.equal(shouldDismissSheet({ offset: 300, velocity: -0.2, sheetHeight: 400 }), false);
    assert.equal(shouldDismissSheet({ offset: 0, velocity: 3, sheetHeight: 400 }), false);
    assert.equal(shouldDismissSheet({ offset: -10, velocity: 3, sheetHeight: 400 }), false);
  });
});

describe("rubber band", () => {
  it("grows with distance but never past its dimension", () => {
    assert.equal(rubberBand(0, 100), 0);
    const a = rubberBand(50, 100);
    const b = rubberBand(500, 100);
    assert.ok(a > 0);
    assert.ok(b > a);
    assert.ok(b < 100);
    assert.ok(rubberBand(50, 100) < 50);
  });

  it("follows the finger 1:1 down to the threshold, then resists", () => {
    assert.equal(sheetDragOffset(60, 400), 60);
    assert.equal(sheetDragOffset(100, 400), 100);
    const past = sheetDragOffset(200, 400);
    assert.ok(past > 100);
    assert.ok(past < 200);
  });

  it("only stretches a little when pulled upward", () => {
    const up = sheetDragOffset(-200, 400);
    assert.ok(up < 0);
    assert.ok(up > -40);
  });
});

describe("classifySheetGesture", () => {
  it("waits inside the slop", () => {
    assert.equal(classifySheetGesture({ dx: 2, dy: 5, canStartDrag: true }), null);
  });

  it("drags on a mostly vertical downward pull when allowed to start", () => {
    assert.equal(classifySheetGesture({ dx: 3, dy: 20, canStartDrag: true }), "drag");
  });

  it("ignores a downward pull when the content under the finger is scrolled", () => {
    assert.equal(classifySheetGesture({ dx: 0, dy: 20, canStartDrag: false }), "ignore");
  });

  it("ignores upward and horizontal gestures", () => {
    assert.equal(classifySheetGesture({ dx: 0, dy: -20, canStartDrag: true }), "ignore");
    assert.equal(classifySheetGesture({ dx: 30, dy: 12, canStartDrag: true }), "ignore");
  });
});
