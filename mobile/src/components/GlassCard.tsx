import React, { useMemo } from 'react';
import { StyleSheet, View, type StyleProp, type ViewStyle } from 'react-native';

import { useThemeMode } from '../context/ThemeModeContext';
import { radii, spacing, type ThemeColors } from '../theme';

/**
 * Static (non-pressable) liquid-glass card: the `lib/glass.ts` fill + rim,
 * `radii.lg` (web panel radius), 1.5 hairline border. Replaces the per-screen copies of
 * "backgroundColor: colors.glass + glassBorder + radii.md" (Players, Waivers,
 * PlayerCompare filter cards and grid cells). Use AnimatedCard when the card
 * is pressable or needs the raised-sheen treatment. `compact` uses
 * `spacing.sm` padding (grid cells).
 */
export default function GlassCard({
  children,
  compact,
  style,
}: {
  children: React.ReactNode;
  compact?: boolean;
  style?: StyleProp<ViewStyle>;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return <View style={[styles.card, compact ? styles.compact : styles.regular, style]}>{children}</View>;
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    card: {
      backgroundColor: colors.glass,
      borderRadius: radii.lg, // web --radius-panel (20)
      borderWidth: StyleSheet.hairlineWidth * 1.5,
      borderColor: colors.glassBorder,
    },
    regular: { padding: spacing.md },
    compact: { padding: spacing.sm },
  });
}
