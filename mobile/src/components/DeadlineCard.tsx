import React, { useMemo } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import AppText from './AppText';
import { useThemeMode } from '../context/ThemeModeContext';
import { deadlineCopy, deadlinePosture, deadlineState, type DeadlineWindow } from '../lib/deadlineMode';
import { LINK_HIT_SLOP, radii, spacing, type ThemeColors } from '../theme';

/**
 * Deadline countdown ("Deadline in 2 weeks: buy a starter"). Mirrors web
 * DeadlineCard: renders nothing unless a real deadline is still ahead.
 * `maxWeeksLeft` hides it until the deadline is near (Dashboard).
 */
export default function DeadlineCard({
  window,
  strategy,
  onPress,
  ctaLabel,
  maxWeeksLeft,
}: {
  window: DeadlineWindow | null | undefined;
  strategy: string | null | undefined;
  onPress?: () => void;
  ctaLabel?: string;
  maxWeeksLeft?: number;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const state = deadlineState(window);
  if (state.phase !== 'open') return null;
  if (maxWeeksLeft !== undefined && (state.weeksLeft === null || state.weeksLeft > maxWeeksLeft)) return null;
  const copy = deadlineCopy(state, deadlinePosture(strategy));
  if (!copy) return null;
  return (
    <View
      testID="deadline-card"
      style={[styles.card, { borderLeftColor: copy.urgent ? colors.danger : colors.accent }]}
    >
      <AppText style={styles.headline}>{copy.headline}</AppText>
      <AppText style={styles.body}>{copy.body}</AppText>
      {onPress && ctaLabel ? (
        <Pressable accessibilityRole="link" hitSlop={LINK_HIT_SLOP} onPress={onPress}>
          <AppText style={styles.link}>{ctaLabel} ›</AppText>
        </Pressable>
      ) : null}
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    card: {
      gap: spacing.xs,
      padding: spacing.md,
      borderRadius: radii.md,
      borderWidth: 1,
      borderLeftWidth: 4,
      borderColor: colors.border,
      backgroundColor: colors.surface,
    },
    headline: { fontSize: 14, fontWeight: '700', color: colors.textPrimary },
    body: { fontSize: 14, color: colors.textSecondary },
    link: { fontSize: 14, fontWeight: '700', color: colors.accent },
  });
}
