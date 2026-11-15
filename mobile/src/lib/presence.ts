// Twin file: web-next/src/lib/presence.ts and mobile/src/lib/presence.ts stay identical.
//
// THE presence rules: a thing that appears or disappears (a toast, a banner, an expander body, a list row, a pill
// layer, a swapped sheet body) animates in and out instead of popping. Pure (no React, no DOM): durations clamped to
// the motion vocabulary's 120-300ms, the reduced-motion switch, the mount / exit-then-unmount phase machine, the
// frames a variant animates between, and the keep-while-leaving merge for list rows. The hook is lib/usePresence.ts;
// the components are web `ui/Presence` and app `Presence`. Opacity, transform and (collapse only) a measured height.

// No imports on purpose: Node's test runner (the app's lib tests) cannot resolve extensionless sibling imports. The numbers
// below equal MOTION_MS.base / .fast and MAX_ANIMATED_ROWS (lib/motion.ts); presence.test.ts guards that on the web.

/** Presence never animates faster or slower than the motion vocabulary's shortest and longest durations. */
export const PRESENCE_MIN_MS = 120;
export const PRESENCE_MAX_MS = 300;
/** Defaults: a thing arrives a little slower than it leaves. */
export const PRESENCE_ENTER_MS = 240;
export const PRESENCE_EXIT_MS = 180;

/** Clamp a requested duration into 120-300ms (a non-number falls back to `fallback`). */
export function clampPresenceMs(ms: number | undefined, fallback: number = PRESENCE_ENTER_MS): number {
  const value = typeof ms === "number" && Number.isFinite(ms) ? ms : fallback;
  return Math.min(PRESENCE_MAX_MS, Math.max(PRESENCE_MIN_MS, Math.round(value)));
}

/** The enter / exit durations to run: clamped to 120-300ms, and 0 for both under reduced motion (the change still
 * happens, instantly: content is simply there, or simply gone). */
export function presenceDurations(opts: { enterMs?: number; exitMs?: number } | undefined, reduced: boolean): { enterMs: number; exitMs: number } {
  if (reduced) return { enterMs: 0, exitMs: 0 };
  return { enterMs: clampPresenceMs(opts?.enterMs, PRESENCE_ENTER_MS), exitMs: clampPresenceMs(opts?.exitMs, PRESENCE_EXIT_MS) };
}

/** exited: not mounted. entering / exiting: mounted and animating. entered: mounted and at rest. */
export type PresencePhase = "exited" | "entering" | "entered" | "exiting";

/** The phase after `show` is applied. Showing from exited/exiting starts an enter (or lands straight on entered when
 * the enter duration is 0); hiding from entering/entered starts an exit (or lands straight on exited when it is 0).
 * Re-showing mid-exit reverses into an enter, re-hiding mid-enter into an exit. Anything else is unchanged. */
export function presenceNext(phase: PresencePhase, show: boolean, d: { enterMs: number; exitMs: number }): PresencePhase {
  if (show && (phase === "exited" || phase === "exiting")) return d.enterMs > 0 ? "entering" : "entered";
  if (!show && (phase === "entering" || phase === "entered")) return d.exitMs > 0 ? "exiting" : "exited";
  return phase;
}

/** The phase once an animation's timer has run out. */
export function presenceSettle(phase: PresencePhase): PresencePhase {
  if (phase === "entering") return "entered";
  if (phase === "exiting") return "exited";
  return phase;
}

/** Whether the content is in the tree at all (anything but exited). */
export function presenceMounted(phase: PresencePhase): boolean {
  return phase !== "exited";
}

/** How long the current phase's animation runs (0 at rest). */
export function presencePhaseMs(phase: PresencePhase, d: { enterMs: number; exitMs: number }): number {
  return phase === "entering" ? d.enterMs : phase === "exiting" ? d.exitMs : 0;
}

/** fade: opacity. rise: opacity + a short lift (toasts, banners). pop: opacity + a small scale (a chip, a badge).
 * collapse: opacity + a measured height (expander bodies, list rows). */
export type PresenceVariant = "fade" | "rise" | "pop" | "collapse";

export interface PresenceFrame {
  opacity: number;
  translateY: number;
  scale: number;
  /** collapse only: 0 (closed) or 1 (fully open, the measured height). */
  openness: number;
}

/** The frame a variant rests at when hidden (`shown: false`) or visible. The app animates between them; the web's CSS
 * (`.presence-*` in globals.css) states the same numbers. */
export function presenceFrame(variant: PresenceVariant, shown: boolean): PresenceFrame {
  if (shown) return { opacity: 1, translateY: 0, scale: 1, openness: 1 };
  return {
    opacity: 0,
    translateY: variant === "rise" ? 8 : 0,
    scale: variant === "pop" ? 0.94 : 1,
    openness: variant === "collapse" ? 0 : 1,
  };
}

/** The frame to show right now for a phase: entered and entering end shown; exiting and exited end hidden. `started`
 * is false on the first paint of an enter (start from hidden, then transition to shown). */
export function presenceTarget(variant: PresenceVariant, phase: PresencePhase, started = true): PresenceFrame {
  const shown = phase === "entered" || (phase === "entering" && started);
  return presenceFrame(variant, shown);
}

/** The pixel height a collapse animates to, never negative or NaN (an unmeasured body opens to its natural height). */
export function collapseTargetPx(measured: number | null | undefined): number | null {
  return typeof measured === "number" && Number.isFinite(measured) && measured > 0 ? Math.round(measured) : null;
}

/** A list row that may be on its way out. */
export interface PresenceEntry<T> {
  key: string;
  item: T;
  /** False while the row plays its exit; it is dropped when that finishes. */
  present: boolean;
}

/** Merge the previous entries with the current items: present items in their new order, and a row that just left stays
 * in the place it was (right after the row that preceded it) with `present: false` until its exit has played. A row
 * that returns before its exit finished is simply present again. */
export function mergePresenceEntries<T>(prev: readonly PresenceEntry<T>[], items: readonly T[], getKey: (item: T) => string): PresenceEntry<T>[] {
  const nextKeys = new Set(items.map(getKey));
  const leaving = new Map<string | null, PresenceEntry<T>[]>();
  let anchor: string | null = null;
  for (const entry of prev) {
    if (nextKeys.has(entry.key)) {
      anchor = entry.key;
    } else {
      const list = leaving.get(anchor) ?? [];
      list.push({ ...entry, present: false });
      leaving.set(anchor, list);
    }
  }
  const out: PresenceEntry<T>[] = [...(leaving.get(null) ?? [])];
  for (const item of items) {
    const key = getKey(item);
    out.push({ key, item, present: true });
    out.push(...(leaving.get(key) ?? []));
  }
  return out;
}

/** The entry list without `key` (its exit finished). */
export function dropPresenceEntry<T>(entries: readonly PresenceEntry<T>[], key: string): PresenceEntry<T>[] {
  return entries.filter((entry) => entry.key !== key);
}

/** Lists past this many rows do not animate rows in or out at all (same cap as every list animation). */
export const MAX_PRESENCE_ROWS = 24;

/** True when a list of `count` rows may animate its adds and removes. */
export function shouldAnimatePresenceList(count: number): boolean {
  return count > 0 && count <= MAX_PRESENCE_ROWS;
}
