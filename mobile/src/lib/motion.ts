// Twin file: web-next/src/lib/motion.ts and mobile/src/lib/motion.ts stay identical.
//
// THE motion vocabulary: durations, easings, stagger, count-up and flash rules, and the performance guards.
// Pure (no React, no DOM). The web mirrors the tokens as CSS variables (--motion-*, --ease-* in globals.css) and the
// app reads them from here. Every animation is opacity/transform only and respects reduced motion.

/** Short, consistent durations in ms (120-300). `instant` is a press/hover response, `slow` the longest entrance. */
export const MOTION_MS = { instant: 120, fast: 180, base: 240, slow: 300 } as const;
export type MotionSpeed = keyof typeof MOTION_MS;

/** Easing curves (cubic-bezier control points), the same on web (CSS `--ease-*`) and the app (`Easing.bezier`). */
export const EASE = {
  out: [0.2, 0.9, 0.3, 1],
  inOut: [0.4, 0, 0.2, 1],
  in: [0.4, 0, 1, 1],
} as const;
export const easeCss = (name: keyof typeof EASE): string => `cubic-bezier(${EASE[name].join(", ")})`;

/** Count-up and flash timings. */
export const COUNT_MS = 450;
export const FLASH_MS = 1100;

/** Lists longer than this do not animate their rows at all (long lists stay instant and cheap). */
export const MAX_ANIMATED_ROWS = 24;
/** Staggers never add more than this much total delay, however many items there are. */
export const MAX_STAGGER_MS = 240;
export const STAGGER_STEP_MS = 40;

/** Duration after the reduced-motion switch: 0 when reduced (the change still happens, instantly). */
export function motionMs(speed: MotionSpeed | number, reduced: boolean): number {
  if (reduced) return 0;
  return typeof speed === "number" ? speed : MOTION_MS[speed];
}

/** Delay of the i-th item of a staggered entrance, capped so the whole group finishes within MAX_STAGGER_MS of the first. */
export function staggerDelay(index: number, count: number, step = STAGGER_STEP_MS): number {
  if (count <= 1 || index <= 0) return 0;
  const perItem = Math.min(step, MAX_STAGGER_MS / Math.max(1, count - 1));
  return Math.round(Math.min(MAX_STAGGER_MS, index * perItem));
}

/** True when a list of `count` rows may animate (entrances, stagger). Long lists stay still. */
export function shouldAnimateList(count: number, max = MAX_ANIMATED_ROWS): boolean {
  return count > 0 && count <= max;
}

/** Which way a value moved, for the score/OVR flash. Null for no change or a missing side. */
export function flashDirection(previous: number | null | undefined, next: number | null | undefined): "up" | "down" | null {
  if (previous == null || next == null || Number.isNaN(previous) || Number.isNaN(next) || previous === next) return null;
  return next > previous ? "up" : "down";
}

/** The eased in-between value of a count-up, t in [0, 1] (cubic ease-out). */
export function countUpValue(from: number, to: number, t: number): number {
  const clamped = Math.min(1, Math.max(0, t));
  const eased = 1 - (1 - clamped) ** 3;
  return from + (to - from) * eased;
}

/** Confetti is rare on purpose: only for a title, never under reduced motion. */
export function confettiAllowed(opts: { wonTitle: boolean; reduced: boolean }): boolean {
  return opts.wonTitle && !opts.reduced;
}

/** Deterministic confetti pieces (angle, distance, delay, hue slot) so the effect is the same every render and testable. */
export function confettiPieces(count = 24): { x: number; y: number; rotate: number; delay: number; hue: number }[] {
  return Array.from({ length: count }, (_, i) => {
    const angle = (i / count) * Math.PI * 2;
    const ring = 0.55 + ((i * 7) % 5) / 10;
    return {
      x: Math.round(Math.cos(angle) * 140 * ring),
      y: Math.round(Math.sin(angle) * 110 * ring - 40),
      rotate: ((i * 47) % 360) - 180,
      delay: (i % 6) * 20,
      hue: i % 4,
    };
  });
}
