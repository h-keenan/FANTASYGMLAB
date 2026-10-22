import React, { useMemo } from 'react';
import { StyleSheet, View } from 'react-native';

import AppText from './AppText';
import { useThemeMode } from '../context/ThemeModeContext';
import { radii, spacing, type ThemeColors } from '../theme';

/**
 * Compact one-box stat strip (value over small label, hairline dividers) —
 * replaces a row of large snapshot tiles on screens that only need two or
 * three headline numbers (Waivers: Available / FAAB / Team need). Mirrors
 * the web Waivers header strip.
 */
export default function StatStrip({ items }: { items: Array<{ label: string; value: string }> }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <View style={styles.box} accessibilityLabel="Summary">
      {items.map((item, index) => (
        <View key={item.label} style={[styles.cell, index > 0 && styles.cellDivider]}>
          <AppText style={styles.value} numberOfLines={1}>
            {item.value}
          </AppText>
          <AppText style={styles.label} numberOfLines={1}>
            {item.label}
          </AppText>
        </View>
      ))}
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    box: {
      flexDirection: 'row',
      alignSelf: 'flex-start',
      borderWidth: StyleSheet.hairlineWidth * 1.5,
      borderColor: colors.cardBorder,
      borderRadius: radii.md,
      backgroundColor: colors.surface,
    },
    cell: { alignItems: 'center', justifyContent: 'center', paddingHorizontal: spacing.md, paddingVertical: spacing.xs + 2 },
    cellDivider: { borderLeftWidth: StyleSheet.hairlineWidth, borderLeftColor: colors.border },
    value: { fontSize: 16, fontWeight: '800', color: colors.textPrimary },
    label: { fontSize: 10, fontWeight: '700', color: colors.textTertiary, textTransform: 'uppercase', letterSpacing: 0.4 },
  });
}
