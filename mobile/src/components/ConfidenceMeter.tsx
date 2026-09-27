import React, { useMemo } from 'react';
import { StyleSheet, View } from 'react-native';

import AppText from './AppText';
import { useThemeMode } from '../context/ThemeModeContext';
import type { ThemeColors } from '../theme';

/**
 * Shared "segmented meter" row — originally Trade Hub's own confidence/
 * realism display (TradeHubScreen.tsx's `MeterRow`), extracted so the same
 * real-signal-backed badge/label pattern can be reused wherever another
 * surface has a genuine, already-computed confidence-like signal to show
 * (Dashboard's Next Move, Waivers' Priority Adds) instead of each screen
 * inventing its own one-off visual language. Trade Hub's own confidence
 * value/scoring is unchanged — this only relocates the existing render, it
 * does not alter what Trade Hub displays or how it's computed.
 */
export const CONFIDENCE_LEVELS: Record<string, number> = { high: 3, medium: 2, low: 1 };

export function confidenceLevelFor(label: string | null | undefined): number {
  return CONFIDENCE_LEVELS[(label ?? '').toLowerCase()] ?? 1;
}

export default function MeterRow({
  label,
  value,
  level,
  color,
}: {
  label: string;
  value: string;
  level: number;
  color: string;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <View style={styles.meter}>
      <AppText style={styles.meterLabel}>{label}</AppText>
      <View style={styles.meterSegments}>
        {[1, 2, 3].map((segment) => (
          <View
            key={segment}
            style={[styles.meterSegment, { backgroundColor: segment <= level ? color : colors.borderStrong }]}
          />
        ))}
      </View>
      <AppText style={[styles.meterValue, { color }]}>{value}</AppText>
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    meter: { flex: 1, flexDirection: 'row', alignItems: 'center', gap: 6 },
    meterLabel: { fontSize: 9, fontWeight: '700', color: colors.textTertiary, letterSpacing: 0.4 },
    meterSegments: { flexDirection: 'row', gap: 3 },
    meterSegment: { width: 14, height: 4, borderRadius: 2 },
    meterValue: { fontSize: 11, fontWeight: '600', color: colors.textSecondary },
  });
}
