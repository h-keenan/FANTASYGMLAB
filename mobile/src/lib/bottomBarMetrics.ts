/**
 * The one set of sizes for the phone bottom region (Advance pill, game orb, tab bar, header), in px.
 * Byte-identical lib twin (scripts/check_lib_twins.mjs): web reads them as CSS custom properties in
 * components/ui/ui.css (bottomBarMetrics.test.ts fails if the two drift), mobile uses them directly, so the
 * footer has the same height, inset and orb offset on every screen and both platforms.
 *
 * Geometry: the pill spans the screen minus `sideInset` on both sides; the orb's right edge sits on the pill's
 * right edge (same inset), `orbGap` above it, so left and right padding are equal by construction.
 */
export const BAR_METRICS = {
  /** Space between the screen edge and the pill (and the orb's right edge), both sides. */
  sideInset: 12,
  /** Gap between the pill and the safe area / screen bottom. */
  pillBottomGap: 8,
  /** Padding between the pill's edge and its button. */
  pillPadding: 4,
  /** Pill border. */
  pillBorder: 1,
  /** Every button in the bar (44 is the minimum tap target). */
  buttonMinHeight: 44,
  /** Floating game orb diameter. */
  orbSize: 56,
  /** Gap between the orb's bottom and the pill's top. */
  orbGap: 4,
  /** Bottom tab bar row height (site shell). */
  tabBarHeight: 52,
  /** Sticky page header height (game header and site shell header). */
  headerHeight: 52,
} as const;

/** Pill height: button + padding both sides + border both sides. */
export const BAR_PILL_HEIGHT = BAR_METRICS.buttonMinHeight + 2 * BAR_METRICS.pillPadding + 2 * BAR_METRICS.pillBorder;

/** Total height the bottom region occupies above the safe area (pill + its gap); content padding below the last row = this + orb + orbGap. */
export const BAR_REGION_HEIGHT = BAR_PILL_HEIGHT + BAR_METRICS.pillBottomGap;

/** Bottom padding the scrolling content needs so the orb never covers the last row. */
export const BAR_CONTENT_CLEARANCE = BAR_REGION_HEIGHT + BAR_METRICS.orbSize + BAR_METRICS.orbGap;
