// Pure decision logic for swiping between tabs (web + mobile twin, byte-identical; no imports).
// The platform layers only gather numbers (touch deltas, start x, whether the touch began inside a horizontal scroller)
// and apply the answers; every "should this swipe count" rule lives here so both platforms agree and it is unit tested.

export type SwipeDecision = "next" | "prev" | "none";
export type SwipeAxis = "horizontal" | "vertical" | "undecided";

/** Movement before an axis is locked (px). */
export const SWIPE_LOCK_SLOP = 10;
/** The horizontal travel must beat the vertical travel by this ratio (about 34 degrees from horizontal). */
export const SWIPE_AXIS_RATIO = 1.5;
/** Travel that commits a swipe without a flick (px). */
export const SWIPE_COMMIT_DISTANCE = 56;
/** A flick this fast (px/ms) commits with a shorter travel. */
export const SWIPE_FLICK_VELOCITY = 0.5;
export const SWIPE_FLICK_MIN_DISTANCE = 24;
/** Touches starting this close to either screen edge belong to the OS back-swipe (web only; mobile passes 0). */
export const SWIPE_EDGE_GUARD = 20;

export interface SwipeStart {
  /** Where the touch began (px from the left of the viewport). */
  startX: number;
  viewportWidth: number;
  /** The touch began inside an element that scrolls horizontally (chip row, depth chart, chart): never hijack it. */
  inHorizontalScroller: boolean;
  /** Edge-guard width in px (SWIPE_EDGE_GUARD on web, 0 on mobile). */
  edgeGuard: number;
}

/** True when a touch starting here may ever become a tab swipe. */
export function swipeMayStart(s: SwipeStart): boolean {
  if (s.inHorizontalScroller) return false;
  if (s.edgeGuard > 0 && (s.startX < s.edgeGuard || s.startX > s.viewportWidth - s.edgeGuard)) return false;
  return true;
}

/** Lock the gesture to an axis once it has moved past the slop; undecided until then. */
export function lockSwipeAxis(dx: number, dy: number): SwipeAxis {
  const ax = Math.abs(dx);
  const ay = Math.abs(dy);
  if (ax < SWIPE_LOCK_SLOP && ay < SWIPE_LOCK_SLOP) return "undecided";
  if (ax >= ay * SWIPE_AXIS_RATIO && ax >= SWIPE_LOCK_SLOP) return "horizontal";
  if (ay > ax) return "vertical";
  return "undecided";
}

/**
 * The outcome of a finished horizontal gesture. Swiping left (negative dx) reveals the next tab, right the previous.
 * `velocityX` is px/ms (signed like dx). No neighbour in that direction means "none" (the caller springs back).
 */
export function decideSwipe(dx: number, dy: number, velocityX: number, hasPrev: boolean, hasNext: boolean): SwipeDecision {
  if (lockSwipeAxis(dx, dy) !== "horizontal") return "none";
  const far = Math.abs(dx) >= SWIPE_COMMIT_DISTANCE;
  const flick = Math.abs(velocityX) >= SWIPE_FLICK_VELOCITY && Math.abs(dx) >= SWIPE_FLICK_MIN_DISTANCE;
  if (!far && !flick) return "none";
  if (dx < 0) return hasNext ? "next" : "none";
  return hasPrev ? "prev" : "none";
}

/**
 * How far the strip's indicator / panel should follow the finger: dx as a fraction of the width (clamped to -1..1),
 * with rubber-banding (a third of the travel) when there is no neighbour on that side.
 */
export function swipeProgress(dx: number, width: number, hasPrev: boolean, hasNext: boolean): number {
  if (width <= 0) return 0;
  let p = Math.max(-1, Math.min(1, dx / width));
  if ((p < 0 && !hasNext) || (p > 0 && !hasPrev)) p /= 3;
  return p;
}

/** The tab key a decision lands on (the current one when there is nothing to move to). */
export function swipeTargetKey(keys: readonly string[], current: string, decision: SwipeDecision): string {
  const i = keys.indexOf(current);
  if (i < 0 || decision === "none") return current;
  const j = decision === "next" ? i + 1 : i - 1;
  return j >= 0 && j < keys.length ? keys[j] : current;
}
