/**
 * Pure math and gesture state machine for swipe-down-to-dismiss on every mobile pop-up (see
 * components/SwipeDismissSheet.tsx). TWIN of web-next/src/lib/sheetGesture.ts: the same rules and numbers so both
 * platforms feel the same; the only difference is the 'worklet' directive on each function (they run on the UI
 * thread inside the pan gesture) and quote style. Keep them in sync (sheetGesture.test.ts runs the same cases
 * on both). Plain TypeScript, so Node's test runner covers it directly.
 */

/** Movement (px) before a touch is classified as a vertical drag, a
 * horizontal gesture, or a scroll. Small enough to feel immediate, large
 * enough that a tap never moves the sheet. */
export const SHEET_DRAG_SLOP_PX = 8;

/** Release velocity (px/ms) that dismisses a short flick. */
export const SHEET_FLICK_VELOCITY = 0.55;

/** A flick still needs to have actually moved the sheet this far, so a
 * fast twitch of a few pixels never closes it. */
export const SHEET_FLICK_MIN_DISTANCE_PX = 40;

/** Vertical must beat horizontal by this factor to claim the gesture; a diagonal in between waits (up to
 * SHEET_AMBIGUOUS_LIMIT_PX) and is then left to the page. Stops a sideways tab-strip swipe that drifts down
 * from grabbing the sheet. */
export const SHEET_AXIS_RATIO = 1.25;
export const SHEET_AMBIGUOUS_LIMIT_PX = 24;

/** Release velocity is measured over this trailing window (ms), not from the last two touch samples: a single
 * jittery sample (1ms apart, 2px moved = 2px/ms) used to dismiss a sheet pulled 24px. */
export const SHEET_VELOCITY_WINDOW_MS = 100;
/** A release this long after the last move is "hold, then let go", not a flick. */
export const SHEET_STALE_MS = 100;
/** Slower than this a release just picks the nearest snap point; faster goes to the next one in its direction. */
export const SHEET_SNAP_FLICK_VELOCITY = 0.35;
/** A scrollTop this close to 0 still counts as the top (Android reports fractional scroll offsets). */
export const SHEET_SCROLL_TOP_TOLERANCE_PX = 1;

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
  /** Release velocity (px/ms); positive is downward. */
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
 * "drag" when it is clearly vertical and allowed (down: `canStartDrag`, the scroll area underneath is at its
 * top or the touch began on the handle; up: `canDragUp`, the sheet is below its top snap point and can expand);
 * "ignore" for horizontal swipes, scrolls inside content that isn't at its top, and diagonals that never
 * resolve; null while still undecided. */
export function classifySheetGesture({
  dx,
  dy,
  canStartDrag,
  canDragUp = false,
}: {
  dx: number;
  dy: number;
  canStartDrag: boolean;
  canDragUp?: boolean;
}): 'drag' | 'ignore' | null {
  'worklet';
  const ax = Math.abs(dx);
  const ay = Math.abs(dy);
  if (ax < SHEET_DRAG_SLOP_PX && ay < SHEET_DRAG_SLOP_PX) return null;
  if (ax > ay) return 'ignore';
  if (ay < ax * SHEET_AXIS_RATIO) return ay >= SHEET_AMBIGUOUS_LIMIT_PX ? 'ignore' : null;
  if (dy > 0) return canStartDrag ? 'drag' : 'ignore';
  return canDragUp ? 'drag' : 'ignore';
}

/** Whether a touch may start dragging the sheet: it began on the grab handle (always allowed), or every scroll
 * area between the finger and the sheet is at its top (`scrollTops` = scrollTop of each scrollable ancestor that
 * actually overflows). Pulling down inside content that is scrolled away from its top scrolls it instead and
 * never closes the sheet. Header and top-area touches have no overflowing ancestor, so they always qualify. */
export function canStartSheetDrag({ onHandle, scrollTops }: { onHandle: boolean; scrollTops: readonly number[] }): boolean {
  'worklet';
  return onHandle || scrollTops.every((top) => top <= SHEET_SCROLL_TOP_TOLERANCE_PX);
}

/** 0..1 for how far a drag has pulled the sheet toward closing; the backdrop fades by this much. */
export function sheetDragProgress(offset: number, sheetHeight: number): number {
  'worklet';
  if (offset <= 0 || sheetHeight <= 0) return 0;
  return Math.min(1, offset / sheetHeight);
}

// ---------------------------------------------------------------------------------------------------------------
// Snap points and the gesture state machine. Everything above is the single-snap special case of this.
//
// Positions are offsets (px) of the sheet from its fully open place: 0 = full, `height * (1 - fraction)` for a
// partly open snap point (a "peek" at 0.5 is `height / 2`), `height` = fully off screen (dismissed). `stops` is
// the ascending list of resting offsets, e.g. [0] (plain sheet), [0, 400] on an 800px sheet with a half-height
// peek. Both platforms run this: web feeds it touch events (lib/useSheetDragDismiss.ts), the app feeds it the
// pan gesture (components/SwipeDismissSheet.tsx).
// ---------------------------------------------------------------------------------------------------------------

/** Resting offsets for snap `fractions` (visible share of the sheet, 1 = full), ascending by offset. */
export function sheetStops(fractions: readonly number[] | undefined, height: number): number[] {
  'worklet';
  const list = fractions && fractions.length > 0 ? fractions : [1];
  const offsets = list.map((f) => Math.round(Math.max(0, Math.min(1, 1 - f)) * Math.max(0, height)));
  return Array.from(new Set(offsets)).sort((a, b) => a - b);
}

/** Index of the stop closest to `position`. */
export function nearestStopIndex(stops: readonly number[], position: number): number {
  'worklet';
  let best = 0;
  for (let i = 1; i < stops.length; i += 1) {
    if (Math.abs(stops[i] - position) < Math.abs(stops[best] - position)) best = i;
  }
  return best;
}

/** On-screen offset for a finger delta from a resting stop (`base`). Between the stops the sheet follows the
 * finger 1:1; above the top stop only a small rubber-band stretch; below the lowest stop 1:1 up to the dismiss
 * distance (so crossing it is felt), then rubber-band resistance. `dismissible: false` resists from the lowest
 * stop right away. */
export function sheetDragPosition({
  base,
  delta,
  stops,
  height,
  dismissible = true,
}: {
  base: number;
  delta: number;
  stops: readonly number[];
  height: number;
  dismissible?: boolean;
}): number {
  'worklet';
  const top = stops[0] ?? 0;
  const bottom = stops[stops.length - 1] ?? 0;
  const raw = base + delta;
  if (raw < top) return top - rubberBand(top - raw, 40);
  const free = dismissible ? sheetDismissDistance(Math.max(0, height - bottom)) : 0;
  if (raw <= bottom + free) return raw;
  return bottom + free + rubberBand(raw - bottom - free, Math.max(height - bottom, free * 2, 1));
}

/** Release velocity (px/ms, positive = downward) from touch samples, over the trailing window. 0 when there
 * are fewer than two usable samples or the last one is stale (the finger rested before lifting). */
export function sheetReleaseVelocity(samples: readonly { y: number; t: number }[], now: number): number {
  'worklet';
  const last = samples[samples.length - 1];
  if (!last || samples.length < 2 || now - last.t > SHEET_STALE_MS) return 0;
  let first = last;
  for (let i = samples.length - 2; i >= 0 && last.t - samples[i].t <= SHEET_VELOCITY_WINDOW_MS; i -= 1) first = samples[i];
  const dt = last.t - first.t;
  return dt > 0 ? (last.y - first.y) / dt : 0;
}

export type SheetRelease = { type: 'dismiss' } | { type: 'snap'; index: number };

/** What a released drag does. Dismiss (only below the lowest stop, only when not moving back up): pulled past
 * the distance threshold OR flicked down fast and far enough. Otherwise settle on a stop: the nearest one, or
 * for a decisive flick the next one in the flick's direction (a flick down from full lands on the peek). */
export function resolveSheetRelease({
  position,
  velocity,
  height,
  stops,
  dismissible = true,
}: {
  position: number;
  velocity: number;
  height: number;
  stops: readonly number[];
  dismissible?: boolean;
}): SheetRelease {
  'worklet';
  const bottom = stops[stops.length - 1] ?? 0;
  const moved = position - bottom;
  if (dismissible && moved > 0 && velocity >= 0) {
    if (moved >= sheetDismissDistance(Math.max(0, height - bottom))) return { type: 'dismiss' };
    if (velocity >= SHEET_FLICK_VELOCITY && moved >= SHEET_FLICK_MIN_DISTANCE_PX) return { type: 'dismiss' };
  }
  if (Math.abs(velocity) >= SHEET_SNAP_FLICK_VELOCITY && stops.length > 1) {
    if (velocity > 0) {
      const next = stops.findIndex((s) => s >= position - 1);
      if (next >= 0) return { type: 'snap', index: next };
    } else {
      for (let i = stops.length - 1; i >= 0; i -= 1) if (stops[i] <= position + 1) return { type: 'snap', index: i };
    }
  }
  return { type: 'snap', index: nearestStopIndex(stops, position) };
}

export interface SheetDragState {
  phase: 'idle' | 'pending' | 'drag' | 'ignored';
  startX: number;
  startY: number;
  /** Where the finger was when the drag was claimed: the drag's offsets are measured from here, so the sheet
   * does not jump by the slop distance. */
  anchorY: number;
  canDown: boolean;
  canUp: boolean;
  base: number;
  position: number;
  stops: number[];
  height: number;
  dismissible: boolean;
  samples: { y: number; t: number }[];
}

export const SHEET_DRAG_IDLE: SheetDragState = {
  phase: 'idle',
  startX: 0,
  startY: 0,
  anchorY: 0,
  canDown: false,
  canUp: false,
  base: 0,
  position: 0,
  stops: [0],
  height: 0,
  dismissible: true,
  samples: [],
};

/** A touch began. `onHandle`: on the grab handle (always allowed to drag). `scrollTops`: scrollTop of every
 * overflowing scroll area between the finger and the sheet. `stopIndex`: the snap point the sheet rests at. */
export function sheetDragStart(input: {
  x: number;
  y: number;
  t: number;
  onHandle: boolean;
  scrollTops: readonly number[];
  height: number;
  stops?: readonly number[];
  stopIndex?: number;
  dismissible?: boolean;
}): SheetDragState {
  'worklet';
  const stops = input.stops && input.stops.length > 0 ? [...input.stops] : [0];
  const stopIndex = Math.min(Math.max(0, input.stopIndex ?? 0), stops.length - 1);
  return {
    phase: 'pending',
    startX: input.x,
    startY: input.y,
    anchorY: input.y,
    canDown: canStartSheetDrag({ onHandle: input.onHandle, scrollTops: input.scrollTops }),
    // Below the top snap point a pull up expands the sheet, from anywhere: its content is not scrollable until it is full.
    canUp: stopIndex > 0,
    base: stops[stopIndex],
    position: stops[stopIndex],
    stops,
    height: input.height,
    dismissible: input.dismissible ?? true,
    samples: [{ y: input.y, t: input.t }],
  };
}

/** A touch moved. Claims the gesture on a clear vertical pull (axis lock), hands it back to the page on
 * anything else, and while dragging returns the new `position` and trailing velocity samples. */
export function sheetDragMove(state: SheetDragState, point: { x: number; y: number; t: number }): SheetDragState {
  'worklet';
  if (state.phase === 'idle' || state.phase === 'ignored') return state;
  if (state.phase === 'pending') {
    const decision = classifySheetGesture({
      dx: point.x - state.startX,
      dy: point.y - state.startY,
      canStartDrag: state.canDown,
      canDragUp: state.canUp,
    });
    if (decision === null) return state;
    if (decision === 'ignore') return { ...state, phase: 'ignored' };
    state = { ...state, phase: 'drag', anchorY: point.y, samples: [{ y: point.y, t: point.t }] };
  }
  const samples = [...state.samples, { y: point.y, t: point.t }].filter((s) => point.t - s.t <= SHEET_VELOCITY_WINDOW_MS * 2);
  return {
    ...state,
    samples,
    position: sheetDragPosition({ base: state.base, delta: point.y - state.anchorY, stops: state.stops, height: state.height, dismissible: state.dismissible }),
  };
}

/** The touch ended: what to do now (null when it was never a drag, so taps and scrolls are untouched). */
export function sheetDragEnd(state: SheetDragState, t: number): SheetRelease | null {
  'worklet';
  if (state.phase !== 'drag') return null;
  return resolveSheetRelease({
    position: state.position,
    velocity: sheetReleaseVelocity(state.samples, t),
    height: state.height,
    stops: state.stops,
    dismissible: state.dismissible,
  });
}
