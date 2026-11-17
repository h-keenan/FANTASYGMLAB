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
  /** Hero entrances (app-only use). */
  emphasized: [0.2, 0, 0, 1],
} as const;
export const easeCss = (name: keyof typeof EASE): string => `cubic-bezier(${EASE[name].join(", ")})`;

/** Count-up and flash timings. */
export const COUNT_MS = 450;
export const FLASH_MS = 1100;

/**
 * THE press feedback (every tappable, web and app): a 3% shrink and a slight fade for `ms`, released on lift.
 * Web: one zero-specificity rule in globals.css ("Press feedback") uses `scale`/`opacity` from these numbers
 * (`--press-scale`, `--press-opacity`); the app's PressableScale and shared Button/GlassCard use them directly.
 * Opt out with `data-no-press` (web) / `pressFeedback={false}` (app) only where a control already animates itself.
 */
export const PRESS = { scale: 0.97, opacity: 0.88, ms: MOTION_MS.instant } as const;

/** The scale and opacity a pressable shows right now. Reduced motion keeps the fade (a colour-like change) and drops the shrink. */
export function pressFeedback(pressed: boolean, reduced: boolean, disabled = false): { scale: number; opacity: number } {
  if (!pressed || disabled) return { scale: 1, opacity: 1 };
  return { scale: reduced ? 1 : PRESS.scale, opacity: PRESS.opacity };
}

/** Transition durations by surface, so a list, a sheet, a tab and a toast do not each invent their own (all within MOTION_MS). */
export const TRANSITION_MS = { page: MOTION_MS.base, sheet: MOTION_MS.slow, tab: MOTION_MS.fast, toast: MOTION_MS.base, list: MOTION_MS.fast, press: MOTION_MS.instant } as const;

/** The success pulse (a saved/claimed/added confirmation): one scale up to this and back, `MOTION_MS.slow`, once. */
export const SUCCESS_PULSE = { scale: 1.08, ms: MOTION_MS.slow } as const;

/** A one-shot hero glow behind a result: fades in over `ms`, then settles at `rest` opacity (never loops). */
export const HERO_GLOW = { ms: 600, rest: 0.55 } as const;

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

// ---------------------------------------------------------------------------
// Motion kit 2 (docs/ui-patterns.md, "Motion spec"): roles, progress, reorder, rank change, concurrency, springs.
// ---------------------------------------------------------------------------

/** The three roles every animation picks from (no new numbers): micro = a press or hover, standard = most state changes, emphasized = an entrance or a landing. */
export const MOTION_ROLE = { micro: MOTION_MS.instant, standard: MOTION_MS.fast, emphasized: MOTION_MS.slow } as const;

/** A progress fill grows over the emphasized duration. It animates `transform: scaleX`, never `width` (compositor-only). */
export const PROGRESS_MS = MOTION_ROLE.emphasized;

/** 0..1 scale of a progress fill from a 0..100 percent (NaN and out-of-range clamp). */
export function progressScale(percent: number | null | undefined): number {
  if (percent == null || Number.isNaN(percent)) return 0;
  return Math.min(1, Math.max(0, percent / 100));
}

/** Rows reorder (FLIP) only up to this many; longer lists just jump (same cap as every other list animation). */
export const MAX_FLIP_ROWS = MAX_ANIMATED_ROWS;

/** The inverse offset a reordered row starts from (old position minus new), or null when it did not move enough to see. */
export function flipOffset(from: { x: number; y: number }, to: { x: number; y: number }, minPx = 2): { dx: number; dy: number } | null {
  const dx = from.x - to.x;
  const dy = from.y - to.y;
  if (Math.abs(dx) < minPx && Math.abs(dy) < minPx) return null;
  return { dx, dy };
}

/** Rank movement for the "up 2" chip: lower rank number is better. Null for no change or a missing side. */
export function rankChange(previous: number | null | undefined, next: number | null | undefined): { dir: "up" | "down"; by: number } | null {
  if (previous == null || next == null || Number.isNaN(previous) || Number.isNaN(next) || previous === next) return null;
  return next < previous ? { dir: "up", by: previous - next } : { dir: "down", by: next - previous };
}

/** How long a rank-change chip stays before it fades. */
export const RANK_CHIP_MS = 2400;

/**
 * Performance cap: at most this many JS-driven (per-frame) animations run at once (number tweens, tick counts).
 * Compositor-only animations (CSS transform/opacity, WAAPI, native-driver) are not counted.
 */
export const MAX_CONCURRENT_TWEENS = 12;
let activeTweens = 0;
/** Reserve a JS tween slot; returns a release function, or null when the cap is reached (the caller then just sets the value). */
export function acquireTween(): (() => void) | null {
  if (activeTweens >= MAX_CONCURRENT_TWEENS) return null;
  activeTweens += 1;
  let released = false;
  return () => {
    if (released) return;
    released = true;
    activeTweens -= 1;
  };
}
export function activeTweenCount(): number {
  return activeTweens;
}

/** App spring presets (react-native Animated.spring, native driver). Press and settle are quick and tight; sheet is the softer landing. Web never springs. */
export const SPRING = {
  press: { damping: 18, stiffness: 320, mass: 0.6 },
  settle: { damping: 20, stiffness: 220, mass: 0.8 },
  sheet: { damping: 26, stiffness: 180, mass: 1 },
  // app-only: pop = overshoot for celebration/reveal, rubber = over-scroll snap-back, fling = velocity handoff after release.
  pop: { damping: 12, stiffness: 260, mass: 0.7 },
  rubber: { damping: 30, stiffness: 400, mass: 1 },
  fling: { damping: 22, stiffness: 140, mass: 1 },
} as const;
export type SpringName = keyof typeof SPRING;

// app-only: durations beyond the 120-300 ladder. `hero` = draw-ins, versus reveal, ticker roll; `epic` = championship only.
export const HERO_MS = { hero: 600, epic: 1400 } as const;
// app-only: ambient loops (compositor transform/opacity only; frozen under Reduce Motion and Reduced effects).
export const AMBIENT_MS = { background: 14000, shimmer: 1600, orbBreath: 4000 } as const;

/** Duration of a role/number, zero when reduced. The ticker roll uses `hero`. */
export function heroMs(speed: keyof typeof HERO_MS, reduced: boolean): number {
  return reduced ? 0 : HERO_MS[speed];
}
