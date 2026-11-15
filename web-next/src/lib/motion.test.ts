import { describe, expect, it } from "vitest";

import { COUNT_MS, MAX_ANIMATED_ROWS, MAX_STAGGER_MS, MOTION_MS, confettiAllowed, confettiPieces, PRESS, TRANSITION_MS, countUpValue, easeCss, pressFeedback, flashDirection, motionMs, shouldAnimateList, staggerDelay } from "./motion";

describe("motion vocabulary", () => {
  it("keeps every duration in the 120-300ms band, ascending", () => {
    const all = Object.values(MOTION_MS);
    expect(Math.min(...all)).toBeGreaterThanOrEqual(120);
    expect(Math.max(...all)).toBeLessThanOrEqual(300);
    expect([...all].sort((a, b) => a - b)).toEqual(all);
    expect(COUNT_MS).toBeGreaterThan(300); // a count-up is the one deliberate exception, still under half a second
    expect(COUNT_MS).toBeLessThan(500);
    expect(easeCss("out")).toBe("cubic-bezier(0.2, 0.9, 0.3, 1)");
  });
  it("reduced motion zeroes every duration", () => {
    expect(motionMs("base", false)).toBe(240);
    expect(motionMs(180, false)).toBe(180);
    expect(motionMs("slow", true)).toBe(0);
    expect(motionMs(180, true)).toBe(0);
  });
  it("a stagger never adds more than the cap in total", () => {
    expect(staggerDelay(0, 5)).toBe(0);
    expect(staggerDelay(1, 1)).toBe(0);
    expect(staggerDelay(2, 5)).toBe(80);
    for (const count of [3, 8, 24, 100]) expect(staggerDelay(count - 1, count)).toBeLessThanOrEqual(MAX_STAGGER_MS);
    expect(staggerDelay(23, 24)).toBe(MAX_STAGGER_MS);
  });
  it("long lists do not animate", () => {
    expect(shouldAnimateList(MAX_ANIMATED_ROWS)).toBe(true);
    expect(shouldAnimateList(MAX_ANIMATED_ROWS + 1)).toBe(false);
    expect(shouldAnimateList(0)).toBe(false);
  });
  it("flash direction and count-up", () => {
    expect(flashDirection(10, 12)).toBe("up");
    expect(flashDirection(12, 10)).toBe("down");
    expect(flashDirection(10, 10)).toBeNull();
    expect(flashDirection(null, 10)).toBeNull();
    expect(countUpValue(0, 100, 0)).toBe(0);
    expect(countUpValue(0, 100, 1)).toBe(100);
    expect(countUpValue(0, 100, 0.5)).toBeGreaterThan(50); // ease-out front-loads the change
    expect(countUpValue(10, 0, 2)).toBe(0);
  });
  it("confetti only for a title and never under reduced motion; pieces are deterministic", () => {
    expect(confettiAllowed({ wonTitle: true, reduced: false })).toBe(true);
    expect(confettiAllowed({ wonTitle: true, reduced: true })).toBe(false);
    expect(confettiAllowed({ wonTitle: false, reduced: false })).toBe(false);
    expect(confettiPieces(24)).toEqual(confettiPieces(24));
    expect(confettiPieces(12)).toHaveLength(12);
  });
});

describe("press feedback (the one press)", () => {
  it("shrinks and fades while pressed, nothing when idle or disabled", () => {
    expect(pressFeedback(true, false)).toEqual({ scale: PRESS.scale, opacity: PRESS.opacity });
    expect(pressFeedback(false, false)).toEqual({ scale: 1, opacity: 1 });
    expect(pressFeedback(true, false, true)).toEqual({ scale: 1, opacity: 1 });
  });
  it("reduced motion keeps the fade but never moves", () => {
    expect(pressFeedback(true, true)).toEqual({ scale: 1, opacity: PRESS.opacity });
  });
  it("every transition duration is one of the shared durations", () => {
    for (const ms of Object.values(TRANSITION_MS)) expect(Object.values(MOTION_MS)).toContain(ms);
  });
});

import { MAX_CONCURRENT_TWEENS, MAX_FLIP_ROWS, MOTION_ROLE, PROGRESS_MS, SPRING, acquireTween, activeTweenCount, flipOffset, progressScale, rankChange } from "./motion";

describe("motion kit 2", () => {
  it("maps the three roles onto existing durations", () => {
    expect(MOTION_ROLE).toEqual({ micro: 120, standard: 180, emphasized: 300 });
    expect(PROGRESS_MS).toBe(300);
  });
  it("clamps a progress percent to a 0-1 scale", () => {
    expect(progressScale(50)).toBe(0.5);
    expect(progressScale(140)).toBe(1);
    expect(progressScale(-5)).toBe(0);
    expect(progressScale(null)).toBe(0);
    expect(progressScale(Number.NaN)).toBe(0);
  });
  it("computes FLIP offsets and ignores sub-visible moves", () => {
    expect(flipOffset({ x: 0, y: 100 }, { x: 0, y: 40 })).toEqual({ dx: 0, dy: 60 });
    expect(flipOffset({ x: 0, y: 100 }, { x: 0, y: 99 })).toBeNull();
    expect(MAX_FLIP_ROWS).toBe(24);
  });
  it("reports rank movement (lower is better)", () => {
    expect(rankChange(5, 3)).toEqual({ dir: "up", by: 2 });
    expect(rankChange(2, 6)).toEqual({ dir: "down", by: 4 });
    expect(rankChange(3, 3)).toBeNull();
    expect(rankChange(null, 3)).toBeNull();
  });
  it("caps concurrent JS tweens and releases slots once", () => {
    const held = Array.from({ length: MAX_CONCURRENT_TWEENS }, () => acquireTween());
    expect(held.every(Boolean)).toBe(true);
    expect(acquireTween()).toBeNull();
    held[0]?.();
    held[0]?.();
    expect(activeTweenCount()).toBe(MAX_CONCURRENT_TWEENS - 1);
    const again = acquireTween();
    expect(again).not.toBeNull();
    again?.();
    held.slice(1).forEach((release) => release?.());
    expect(activeTweenCount()).toBe(0);
  });
  it("has quick, tight press and settle springs", () => {
    expect(SPRING.press.stiffness).toBeGreaterThan(SPRING.sheet.stiffness);
  });
});
