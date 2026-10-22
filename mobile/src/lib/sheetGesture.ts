/**
 * Pure math for swipe-down-to-dismiss on every mobile pop-up (see
 * components/SwipeDismissSheet.tsx). The same rules and numbers as
 * web-next's lib/sheetGesture.ts, so both platforms feel the same. Each
 * function is a Reanimated worklet (it runs on the UI thread inside the
 * pan gesture) and stays plain TypeScript, so Node's test runner covers
 * it directly (sheetGesture.test.ts).
 *
 * Owner, 2026-10-21: 'I would still like a gesture to swipe down out of
 * the PQV, or any other pop-up windows.'
 */

/** Movement (px) before a touch is classified as a vertical drag, a
 * horizontal gesture, or a scroll. Small enough to feel immediate, large
 * enough that a tap never moves the sheet. */
export const SHEET_DRAG_SLOP_PX = 8;

/** Release velocity (px/ms) that dismisses a short flick. */
export const SHEET_FLICK_VELOCITY = 0.5;

/** A flick still needs to have actually moved the sheet this far, so a
 * fast twitch of a few pixels never closes it. */
export const SHEET_FLICK_MIN_DISTANCE_PX = 24;

/** Distance threshold: a quarter of the sheet's height, clamped so a tiny
 * sheet still needs a deliberate pull and a tall one doesn't need a
 * half-screen drag. */
export function sheetDismissDistance(sheetHeight: number): number {
  'worklet';
  const quarter = sheetHeight > 0 ? sheetHeight * 0.25 : 120;
  return Math.min(160, Math.max(80, quarter));
}

/** Whether a released drag closes the sheet: pulled past the distance
 * threshold, or flicked downward fast enough (and far enough). A drag
 * released while moving back up never dismisses. */
export function shouldDismissSheet({
  offset,
  velocity,
  sheetHeight,
}: {
  /** Current downward offset (px) of the sheet. */
  offset: number;
  /** Release velocity (px/ms); positive is downward. Gesture handler
   * reports px/s, so callers divide by 1000. */
  velocity: number;
  sheetHeight: number;
}): boolean {
  'worklet';
  if (offset <= 0) return false;
  if (velocity < 0) return false;
  if (offset >= sheetDismissDistance(sheetHeight)) return true;
  return velocity >= SHEET_FLICK_VELOCITY && offset >= SHEET_FLICK_MIN_DISTANCE_PX;
}

/** iOS-style rubber band: the further past the edge, the less the sheet
 * follows the finger. `dimension` bounds how far it can ever travel. */
export function rubberBand(distance: number, dimension: number, constant = 0.55): number {
  'worklet';
  if (distance <= 0 || dimension <= 0) return 0;
  return (1 - 1 / ((distance * constant) / dimension + 1)) * dimension;
}

/** The on-screen offset for a raw finger delta. Downward follows the
 * finger 1:1 up to the dismiss distance, then with rubber-band resistance,
 * so crossing the threshold is felt. Upward (past the sheet's resting
 * position) only gives a small rubber-band stretch. */
export function sheetDragOffset(delta: number, sheetHeight: number): number {
  'worklet';
  if (delta < 0) return -rubberBand(-delta, 40);
  const threshold = sheetDismissDistance(sheetHeight);
  if (delta <= threshold) return delta;
  return threshold + rubberBand(delta - threshold, Math.max(sheetHeight, threshold * 2));
}

/** Classifies the start of a touch gesture once it moves past the slop:
 * 'drag' when it is mostly vertical, downward, and allowed to start (the
 * scroll area underneath is at its top, or the touch began on the handle);
 * 'ignore' for horizontal swipes, upward scrolls, and scrolls inside
 * content that isn't at its top; null while still inside the slop. */
export function classifySheetGesture({
  dx,
  dy,
  canStartDrag,
}: {
  dx: number;
  dy: number;
  canStartDrag: boolean;
}): 'drag' | 'ignore' | null {
  'worklet';
  if (Math.abs(dx) < SHEET_DRAG_SLOP_PX && Math.abs(dy) < SHEET_DRAG_SLOP_PX) return null;
  if (Math.abs(dx) > Math.abs(dy)) return 'ignore';
  if (dy <= 0) return 'ignore';
  return canStartDrag ? 'drag' : 'ignore';
}
