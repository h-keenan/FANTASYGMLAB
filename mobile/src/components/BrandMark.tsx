import React from 'react';
import { Image } from 'react-native';

/**
 * The FantasyGM Lab brand mark — the glossy 3D football-with-ascending-bars
 * illustration that PRs #749/#750 rolled out to every static app icon and
 * logo file, replacing the old abstract three-arc "Analyze / Project /
 * Execute" bezier mark.
 *
 * This component used to be `TrajectoryArcs`: it hand-drew that OLD arc
 * mark's exact bezier geometry live in code (recolored with theme tokens)
 * because, at the time, the arc mark only existed baked into a static icon
 * PNG and nowhere else it could be reused live (splash/loading, the GM orb,
 * the dashboard empty state). PRs #749/#750 replaced the static icon, but
 * missed this component, so those three surfaces kept animating the
 * *retired* brand mark on-screen after every other icon/logo had already
 * moved on.
 *
 * The new mark is a complex glossy 3D illustration, not a simple geometric
 * shape — redrawing it as hand-authored SVG paths would look worse than the
 * genuine artwork, so this just renders the same transparent-background
 * mark asset already used for the splash screen (`assets/splash-icon.png`,
 * swapped in by PR #749) scaled to fit. That keeps this in permanent sync
 * with whatever the current static brand mark is, instead of drifting out
 * of date again.
 */
export default function BrandMark({ width = 160, height = 108 }: { width?: number; height?: number }) {
  return (
    <Image
      // eslint-disable-next-line @typescript-eslint/no-require-imports
      source={require('../../assets/splash-icon.png')}
      style={{ width, height }}
      resizeMode="contain"
      accessibilityElementsHidden
      importantForAccessibility="no-hide-descendants"
    />
  );
}
