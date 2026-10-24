import React from 'react';
import { View } from 'react-native';

import { useThemeMode } from '../context/ThemeModeContext';
import { overallRatingColor } from '../lib/percentile';
import CircularProgressRing from './CircularProgressRing';

/**
 * The one "NN OVR" rendering in the app, mirroring the web's `OvrGauge`
 * (web-next/src/components/OvrGauge.tsx -> ValueRing): a circular gauge whose
 * arc fills `rating`% and whose arc + number take the shared red -> gold ->
 * green tint (`overallRatingColor`, web `overallRatingTint`). Diameters match
 * the web ring sizes (xs 1.65rem, sm 2.5rem, md 3.25rem, lg 4.5rem at 16px).
 * `rating` null renders nothing (no fabricated rating) unless `reserveSpace`
 * keeps the footprint so a column stays aligned, as the web does.
 */
export type OvrGaugeSize = 'xs' | 'sm' | 'md' | 'lg';

// diameter, stroke (web punched-out inset), font px (web .value-ring-value)
export const OVR_GAUGE_SPEC: Record<OvrGaugeSize, { diameter: number; stroke: number; font: number }> = {
  xs: { diameter: 26, stroke: 3.5, font: 9 },
  sm: { diameter: 40, stroke: 4.8, font: 12 },
  md: { diameter: 52, stroke: 4.8, font: 16 },
  lg: { diameter: 72, stroke: 7.2, font: 20 },
};

export default function OvrGauge({
  rating,
  size = 'sm',
  label,
  color,
  reserveSpace = false,
}: {
  rating: number | null | undefined;
  size?: OvrGaugeSize;
  /** Optional caption under the ring (e.g. "OVR"). */
  label?: string;
  /** Override the rating tint (e.g. a top-5 prestige color). */
  color?: string;
  reserveSpace?: boolean;
}) {
  const { colors } = useThemeMode();
  const spec = OVR_GAUGE_SPEC[size];
  if (rating === null || rating === undefined || !Number.isFinite(rating)) {
    return reserveSpace ? <View style={{ width: spec.diameter, height: spec.diameter }} accessibilityElementsHidden /> : null;
  }
  const clamped = Math.max(0, Math.min(99, Math.round(rating)));
  return (
    <View accessible accessibilityRole="image" accessibilityLabel={`${clamped} overall rating`}>
      <CircularProgressRing
        percent={clamped}
        size={spec.diameter}
        strokeWidth={spec.stroke}
        color={color ?? overallRatingColor(clamped, colors)}
        valueLabel={String(clamped)}
        valueFontScale={spec.font / spec.diameter}
        label={label}
      />
    </View>
  );
}
