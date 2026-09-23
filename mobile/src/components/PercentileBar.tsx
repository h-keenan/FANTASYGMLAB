import React, { useMemo } from 'react';
import { StyleSheet, View } from 'react-native';

import { useThemeMode } from '../context/ThemeModeContext';
import { percentileColor } from '../lib/percentile';
import { radii, type ThemeColors } from '../theme';

/**
 * Thin percentile progress indicator for MetricCard — a strong percentile
 * fills further and reads green, a weak one reads amber/red, per
 * coridian_'s concept-sheet ask. Purely a renderer over an existing
 * 0-100 percentile the backend already computed; never a second bar for the
 * raw stat value itself (see PercentBar in PlayerDetailScreen for that,
 * still used by the Usage section's snap-share/target-share bars).
 */
export default function PercentileBar({ percentile }: { percentile: number | null | undefined }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  if (percentile === null || percentile === undefined || !Number.isFinite(percentile)) return null;
  const clamped = Math.max(0, Math.min(100, percentile));
  const tint = percentileColor(clamped, colors);
  return (
    <View style={styles.track}>
      <View style={[styles.fill, { width: `${clamped}%`, backgroundColor: tint }]} />
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    track: {
      height: 4,
      borderRadius: radii.pill,
      backgroundColor: colors.backgroundElevated,
      overflow: 'hidden',
      marginTop: 6,
    },
    fill: {
      height: '100%',
      borderRadius: radii.pill,
    },
  });
}
