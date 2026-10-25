import React, { useMemo } from 'react';
import { StyleSheet, View } from 'react-native';

import AppText from './AppText';
import { useThemeMode } from '../context/ThemeModeContext';
import { type ThemeColors } from '../theme';

/**
 * A value number with its small "Value" caption above it (owner decision 3:
 * the label is small, above the number, everywhere). Mirrors web-next's
 * ValueStat.
 */
export default function ValueStat({
  value,
  label = 'Value',
  align = 'flex-end',
  size = 'md',
  color,
}: {
  value: string | number | null | undefined;
  label?: string;
  align?: 'flex-start' | 'center' | 'flex-end';
  /** `lg` is the hero number (My Team header). */
  size?: 'md' | 'lg';
  /** Tint for a signed gain/loss number; defaults to primary text. */
  color?: string;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  if (value === null || value === undefined || value === '') return null;
  return (
    <View style={[styles.wrap, { alignItems: align }]}>
      <AppText style={styles.label}>{label}</AppText>
      <AppText style={[styles.value, size === 'lg' && styles.valueLg, color ? { color } : null]}>{typeof value === 'number' ? Math.round(value).toLocaleString() : value}</AppText>
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    wrap: { justifyContent: 'center' },
    label: { fontSize: 9, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.6, color: colors.textTertiary },
    valueLg: { fontSize: 24 },
    value: { fontSize: 15, fontWeight: '800', color: colors.textPrimary },
  });
}
