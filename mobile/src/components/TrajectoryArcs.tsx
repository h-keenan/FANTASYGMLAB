import React from 'react';
import Svg, { Circle, Path, Polygon } from 'react-native-svg';

import { colors } from '../theme';

/**
 * The three-arc "Analyze / Project / Execute" trajectory motif from the
 * brand concept sheet's "CONCEPT DIRECTIONS" / "APPLICATIONS" panels — the
 * mark currently only exists baked into the static app icon PNG (PR #596),
 * not reused anywhere the concept sheet shows it (splash/loading, empty
 * states, success confirmations, share cards). Geometry below is the exact
 * same three cubic-bezier arcs from mobile/assets/brand/app-icon-1024.svg's
 * `<g transform="translate(75,55) scale(.86)">` group, with that transform
 * baked into the numbers (rather than re-deriving the curves by eye) so
 * this reads as the identical mark wherever it appears, cropped to just the
 * arc region instead of the full icon canvas.
 */
export default function TrajectoryArcs({ width = 160, height = 108 }: { width?: number; height?: number }) {
  return (
    <Svg width={width} height={height} viewBox="150 60 700 470" fill="none">
      <Path
        d="M212.6 347.4 C376 123.8 565.2 132.4 728.6 295.8"
        stroke={colors.accent}
        strokeWidth={41.3}
        strokeLinecap="round"
        fill="none"
      />
      <Path
        d="M229.8 407.6 C393.2 201.2 582.4 201.2 754.4 330.2"
        stroke={colors.premium}
        strokeWidth={41.3}
        strokeLinecap="round"
        fill="none"
      />
      <Path
        d="M247 467.8 C410.4 287.2 599.6 270 780.2 373.2"
        stroke={colors.danger}
        strokeWidth={41.3}
        strokeLinecap="round"
        fill="none"
      />
      <Circle cx={212.6} cy={347.4} r={20.6} fill={colors.background} stroke={colors.accent} strokeWidth={15.5} />
      <Circle cx={229.8} cy={407.6} r={20.6} fill={colors.background} stroke={colors.premium} strokeWidth={15.5} />
      <Circle cx={247} cy={467.8} r={20.6} fill={colors.background} stroke={colors.danger} strokeWidth={15.5} />
      <Polygon points="728.6,295.8 677,261.4 701.1,325.9" fill={colors.accent} />
      <Polygon points="754.4,330.2 702.8,295.8 726.9,360.3" fill={colors.premium} />
      <Polygon points="780.2,373.2 728.6,338.8 752.7,403.3" fill={colors.danger} />
    </Svg>
  );
}
