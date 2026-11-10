import React, { useMemo } from 'react';
import { StyleSheet, View } from 'react-native';

import AppText from './AppText';
import ToneBadge from './ToneBadge';
import type { TradePosture } from '../lib/api';
import { useThemeMode } from '../context/ThemeModeContext';
import { spacing, type ThemeColors } from '../theme';

/**
 * The team posture a trade verdict was graded under (modules/trade_posture.py):
 * the shared ToneBadge pill plus a one-line "why". Mirrors web-next's
 * PostureChip. Neutral tint on purpose: a posture is context, not good or bad
 * news. The override is the existing Team Situation / GM Stance control.
 * Theme-aware: reads colors from useThemeMode, never the static dark palette.
 */
export default function PostureChip({ posture }: { posture: TradePosture }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <View style={styles.row} testID="posture-chip" accessibilityLabel={`Graded as a ${posture.label} team. ${posture.why}`}>
      <ToneBadge label={posture.label} color={colors.accent} />
      <AppText style={styles.why}>{posture.why}</AppText>
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    row: { flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', gap: spacing.xs, marginBottom: spacing.xs },
    why: { fontSize: 13.5, color: colors.textTertiary, flexShrink: 1 },
  });
}
