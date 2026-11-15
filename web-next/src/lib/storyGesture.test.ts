import { describe, expect, it } from "vitest";

import {
  SHEET_PROFILE,
  STORY_PROFILE,
  SHEET_DRAG_IDLE,
  classifySheetGesture,
  sheetDismissDistance,
  sheetDragEnd,
  sheetDragMove,
  sheetDragStart,
  shouldDismissSheet,
  type SheetGestureProfile,
  type SheetDragState,
} from "./sheetGesture";

// The recap story's forgiving gesture profile (docs/ui-patterns.md "Gestures"): thresholds, plus noisy simulated
// swipes. The same file runs on the app (mobile/src/lib/storyGesture.test.ts): both platforms share the rules.

const H = 844; // a phone-height full-screen card

describe("STORY_PROFILE thresholds", () => {
  it("releases at 12% of the height, clamped to 56..100px (standard sheets stay 25%, 80..160)", () => {
    expect(sheetDismissDistance(H, STORY_PROFILE)).toBe(100);
    expect(sheetDismissDistance(600, STORY_PROFILE)).toBe(72);
    expect(sheetDismissDistance(300, STORY_PROFILE)).toBe(56);
    expect(sheetDismissDistance(H)).toBe(160);
    expect(sheetDismissDistance(H, SHEET_PROFILE)).toBe(160);
  });

  it("uses a 12px axis lock and no diagonal dead zone; a mostly-sideways swipe is never claimed", () => {
    const base = { canStartDrag: true };
    expect(classifySheetGesture({ ...base, dx: 0, dy: 11, profile: STORY_PROFILE })).toBeNull();
    expect(classifySheetGesture({ ...base, dx: 0, dy: 12, profile: STORY_PROFILE })).toBe("drag");
    // A 12px-ish pull with 10px of sideways drift is still a pull for the story, but waits for the standard sheet.
    expect(classifySheetGesture({ ...base, dx: 11, dy: 13, profile: STORY_PROFILE })).toBe("drag");
    expect(classifySheetGesture({ ...base, dx: 11, dy: 13 })).toBeNull();
    // Horizontal story swipes keep the page.
    expect(classifySheetGesture({ ...base, dx: 40, dy: 14, profile: STORY_PROFILE })).toBe("ignore");
    expect(classifySheetGesture({ ...base, dx: -30, dy: 12, profile: STORY_PROFILE })).toBe("ignore");
  });

  it("flicks at 0.4px/ms over 32px; the standard sheet still needs 0.55px/ms over 40px", () => {
    expect(shouldDismissSheet({ offset: 34, velocity: 0.4, sheetHeight: H, profile: STORY_PROFILE })).toBe(true);
    expect(shouldDismissSheet({ offset: 34, velocity: 0.39, sheetHeight: H, profile: STORY_PROFILE })).toBe(false);
    expect(shouldDismissSheet({ offset: 30, velocity: 2, sheetHeight: H, profile: STORY_PROFILE })).toBe(false);
    expect(shouldDismissSheet({ offset: 34, velocity: 0.45, sheetHeight: H })).toBe(false);
    expect(shouldDismissSheet({ offset: 100, velocity: 0, sheetHeight: H, profile: STORY_PROFILE })).toBe(true);
    expect(shouldDismissSheet({ offset: 99, velocity: 0, sheetHeight: H, profile: STORY_PROFILE })).toBe(false);
  });

  it("treats a hair of upward jitter as rest but a real pull back up as cancel", () => {
    expect(shouldDismissSheet({ offset: 120, velocity: -0.1, sheetHeight: H, profile: STORY_PROFILE })).toBe(true);
    expect(shouldDismissSheet({ offset: 120, velocity: -0.3, sheetHeight: H, profile: STORY_PROFILE })).toBe(false);
    expect(shouldDismissSheet({ offset: 200, velocity: -0.1, sheetHeight: H })).toBe(false);
  });

  it("is only opt-in: every other call site keeps the standard numbers", () => {
    expect(SHEET_PROFILE.slopPx).toBe(8);
    expect(SHEET_PROFILE.axisRatio).toBe(1.25);
    expect(SHEET_DRAG_IDLE.profile).toBe(SHEET_PROFILE);
  });
});

// --- noisy-swipe trials ----------------------------------------------------------------------------------------------
// Simulated fingers: jitter, diagonal drift, slow drags and flicks. Deterministic (seeded) so a failure reproduces.

function rng(seed: number) {
  let s = seed >>> 0;
  return () => {
    s = (Math.imul(s, 1664525) + 1013904223) >>> 0;
    return s / 4294967296;
  };
}

type Trial = { dx: number; dy: number; ms: number; jitter: number; backTo?: number };

/** Touch samples every 16ms along (0,0) -> (dx,dy) with ease-in-out, x/y jitter, then optional return to `backTo` of dy. */
function path(t: Trial, rand: () => number) {
  const pts: Array<{ x: number; y: number; t: number }> = [{ x: 200, y: 400, t: 0 }];
  const n = Math.max(3, Math.round(t.ms / 16));
  for (let i = 1; i <= n; i += 1) {
    const p = i / n;
    const eased = t.ms >= 300 ? p * p * (3 - 2 * p) : p;
    pts.push({ x: 200 + t.dx * eased + (rand() - 0.5) * 2 * t.jitter, y: 400 + t.dy * eased + (rand() - 0.5) * 2 * t.jitter, t: i * 16 });
  }
  if (t.backTo !== undefined) {
    const last = pts[pts.length - 1];
    for (let i = 1; i <= 6; i += 1) pts.push({ x: last.x, y: last.y + (t.dy * t.backTo - t.dy) * (i / 6) + (rand() - 0.5) * t.jitter, t: last.t + i * 16 });
  }
  return pts;
}

function run(points: Array<{ x: number; y: number; t: number }>, profile: SheetGestureProfile) {
  const [first, ...rest] = points;
  let state: SheetDragState = sheetDragStart({ x: first.x, y: first.y, t: first.t, onHandle: false, scrollTops: [], height: H, profile });
  for (const p of rest) state = sheetDragMove(state, p);
  const end = points[points.length - 1].t + 4;
  return { phase: state.phase, release: sheetDragEnd(state, end) };
}

function dismisses(points: Array<{ x: number; y: number; t: number }>, profile: SheetGestureProfile) {
  return run(points, profile).release?.type === "dismiss";
}

describe("noisy swipe trials (story profile)", () => {
  it("dismisses a sloppy but intentional slow down swipe: jitter, diagonal drift, 160-300px of finger travel over 0.4-1.4s (the 12px slop is not counted by the pull)", () => {
    const rand = rng(7);
    for (let i = 0; i < 200; i += 1) {
      const dy = 160 + rand() * 140;
      const drift = (rand() - 0.5) * 2 * dy * 0.55; // up to 55% of the pull sideways, either way
      const trial: Trial = { dx: drift, dy, ms: 400 + rand() * 1000, jitter: 3 + rand() * 3 };
      const pts = path(trial, rand);
      expect(dismisses(pts, STORY_PROFILE)).toBe(true);
    }
  });

  it("dismisses a quick flick of 60-110px in 90-140ms", () => {
    const rand = rng(11);
    for (let i = 0; i < 200; i += 1) {
      const dy = 60 + rand() * 50;
      const trial: Trial = { dx: (rand() - 0.5) * 24, dy, ms: 90 + rand() * 50, jitter: 1.5 };
      // The flick must actually be >= 0.4px/ms for its own length, otherwise it is not a flick (guard the generator).
      if (dy / trial.ms < 0.6) continue;
      expect(dismisses(path(trial, rand), STORY_PROFILE)).toBe(true);
    }
  });

  it("the standard sheet profile would NOT have closed the same sloppy slow swipes (why the story needs its own)", () => {
    const rand = rng(7);
    let missed = 0;
    for (let i = 0; i < 100; i += 1) {
      const dy = 110 + rand() * 40; // under the standard 160px
      const trial: Trial = { dx: (rand() - 0.5) * dy, dy, ms: 600 + rand() * 600, jitter: 4 };
      if (!dismisses(path(trial, rand), SHEET_PROFILE)) missed += 1;
    }
    expect(missed).toBeGreaterThan(80);
  });

  it("does not dismiss accidental jitter or a short slow pull (under 12px slop or 30px)", () => {
    const rand = rng(23);
    for (let i = 0; i < 200; i += 1) {
      const dy = rand() * 28;
      const trial: Trial = { dx: (rand() - 0.5) * 20, dy, ms: 60 + rand() * 900, jitter: 3 };
      expect(dismisses(path(trial, rand), STORY_PROFILE)).toBe(false);
    }
  });

  it("does not dismiss a pull that is brought back up before release", () => {
    const rand = rng(31);
    for (let i = 0; i < 100; i += 1) {
      const trial: Trial = { dx: (rand() - 0.5) * 20, dy: 90 + rand() * 120, ms: 500, jitter: 3, backTo: 0.1 + rand() * 0.1 };
      expect(dismisses(path(trial, rand), STORY_PROFILE)).toBe(false);
    }
  });

  it("never claims or dismisses a horizontal story swipe, even with downward wobble", () => {
    const rand = rng(41);
    for (let i = 0; i < 200; i += 1) {
      const dx = (rand() < 0.5 ? -1 : 1) * (70 + rand() * 180);
      const trial: Trial = { dx, dy: Math.abs(dx) * rand() * 0.6, ms: 120 + rand() * 500, jitter: 3 };
      const result = run(path(trial, rand), STORY_PROFILE);
      expect(result.release).toBeNull();
      expect(result.phase).not.toBe("drag");
    }
  });

  it("never dismisses a pull upward", () => {
    const rand = rng(53);
    for (let i = 0; i < 50; i += 1) {
      expect(dismisses(path({ dx: (rand() - 0.5) * 30, dy: -(60 + rand() * 200), ms: 150 + rand() * 600, jitter: 3 }, rand), STORY_PROFILE)).toBe(false);
    }
  });
});
