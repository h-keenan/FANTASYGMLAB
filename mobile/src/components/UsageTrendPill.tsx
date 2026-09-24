import React, { useMemo } from 'react';
import { StyleSheet, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import AppText from './AppText';
import { useThemeMode } from '../context/ThemeModeContext';
import type { UsageTrend } from '../lib/api';
import { radii, spacing, type ThemeColors } from '../theme';

/**
 * Inline usage-trend pill for a ranked row — arrow plus the signed move, no
 * words, because the row it sits in is already dense; Player Detail carries
 * the full "trending up (high confidence)" sentence. The server only sends a
 * usage_trend at all once the read clears its confidence gate
 * (modules/rankings.py: recency_trend_display), so there is nothing to
 * threshold here.
 *
 * Promoted out of PlayersScreen's own private copy so GM Targets (and any
 * future ranked-row list) can share the exact same treatment instead of a
 * second near-identical implementation — Magna Carta §44/§45.
 */
export default function UsageTrendPill({ trend }: { trend: UsageTrend }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const rising = trend.direction === 'up';
  const tint = rising ? colors.success : colors.danger;
  return (
    <View
      style={[
        styles.trendPill,
        { backgroundColor: rising ? colors.successMuted : colors.dangerMuted, borderColor: tint },
      ]}
    >
      <Ionicons name={rising ? 'arrow-up' : 'arrow-down'} size={9} color={tint} />
      <AppText style={[styles.trendPillText, { color: tint }]}>{trend.magnitude_pct}%</AppText>
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    // Geometry copied from PositionBadge/PlayerIdentityRow's own chips so
    // the trend pill reads as one family of inline tags with them.
    trendPill: {
      flexDirection: 'row',
      alignItems: 'center',
      alignSelf: 'flex-start',
      gap: 1,
      paddingHorizontal: spacing.xs + 2,
      paddingVertical: 1,
      borderRadius: radii.pill,
      borderWidth: 1,
    },
    trendPillText: { fontSize: 9, fontWeight: '800', letterSpacing: 0.3 },
  });
}
