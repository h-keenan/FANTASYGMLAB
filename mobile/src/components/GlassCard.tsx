import React, { useMemo } from 'react';
import { StyleSheet, View, type StyleProp, type ViewStyle } from 'react-native';

import { useThemeMode } from '../context/ThemeModeContext';
import { radii, spacing, type ThemeColors } from '../theme';

/**
 * Surface decision table (which card to reach for; none of these is deprecated,
 * they do different jobs, so a screen-local `colors.glass + glassBorder +
 * radii.*` copy is the thing to migrate here):
 *   static content card .......... GlassCard (this file)
 *   pressable / raised sheen ..... AnimatedCard
 *   semantic left rail ........... AccentCard (AnimatedCard + 3pt rail)
 *   one-off blurred hero/header .. GlassPanel (live blur, never in lists)
 *   stat tile with percentile .... MetricCard (label/value/bar, not a container)
 *
 * Static (non-pressable) liquid-glass card: the `lib/glass.ts` fill + rim,
 * `radii.lg` (web panel radius), 1.5 hairline border. Replaces the per-screen copies of
 * "backgroundColor: colors.glass + glassBorder + radii.md" (Players, Waivers,
 * PlayerCompare filter cards and grid cells). Use AnimatedCard when the card
 * is pressable or needs the raised-sheen treatment. `compact` uses
 * `spacing.sm` padding (grid cells); `padding` picks sm/md/lg explicitly and
 * `radius` picks `radii.md` (14) for the denser in-page cards that never took
 * the web panel radius, so those migrate here with no visual change.
 */
export default function GlassCard({
  children,
  compact,
  padding,
  radius = 'lg',
  style,
}: {
  children: React.ReactNode;
  compact?: boolean;
  /** Overrides `compact`. Default md. */
  padding?: 'sm' | 'md' | 'lg';
  radius?: 'md' | 'lg';
  style?: StyleProp<ViewStyle>;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const pad = padding ?? (compact ? 'sm' : 'md');
  return <View style={[styles.card, radius === 'md' && styles.radiusMd, styles[pad], style]}>{children}</View>;
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    card: {
      backgroundColor: colors.glass,
      borderRadius: radii.lg, // web --radius-panel (20)
      borderWidth: StyleSheet.hairlineWidth * 1.5,
      borderColor: colors.glassBorder,
    },
    radiusMd: { borderRadius: radii.md },
    sm: { padding: spacing.sm },
    md: { padding: spacing.md },
    lg: { padding: spacing.lg },
  });
}
