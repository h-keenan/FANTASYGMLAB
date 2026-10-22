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
export default function StatStrip({
  items,
  fullWidth = false,
}: {
  items: Array<{ label: string; value: string; tone?: 'positive' | 'risk' }>;
  fullWidth?: boolean;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <View style={[styles.box, fullWidth && styles.boxFull]} accessibilityLabel="Summary">
      {items.map((item, index) => (
        <View key={item.label} style={[styles.cell, fullWidth && styles.cellFull, index > 0 && styles.cellDivider]}>
          <AppText
            style={[
              styles.value,
              item.tone === 'positive' && { color: colors.successBright },
              item.tone === 'risk' && { color: colors.danger },
            ]}
            numberOfLines={1}
          >
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
    boxFull: { alignSelf: 'stretch' },
    cellFull: { flex: 1, paddingHorizontal: spacing.xs },
    cellDivider: { borderLeftWidth: StyleSheet.hairlineWidth, borderLeftColor: colors.border },
    value: { fontSize: 16, fontWeight: '800', color: colors.textPrimary },
    label: { fontSize: 10, fontWeight: '700', color: colors.textTertiary, textTransform: 'uppercase', letterSpacing: 0.4 },
  });
}
