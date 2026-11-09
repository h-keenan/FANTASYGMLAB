import React from 'react';
import { StyleSheet, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import AppText from './AppText';
import { withAlpha } from './ToneBadge';
import { useThemeMode } from '../context/ThemeModeContext';
import { radii, spacing } from '../theme';

/**
 * Shared header pieces for the Trade History and Community trade cards
 * (mirrors web-next's TradeOutcomeHeader): a tinted swap glyph tile, a
 * lettered A/B pair for anonymous teams, and a centered net-edge bar.
 */

export function TradeSwapGlyph({ color, size = 36 }: { color: string; size?: number }) {
  return (
    <View
      style={{
        width: size,
        height: size,
        borderRadius: size / 2,
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: withAlpha(color, 0.15),
        borderWidth: 1,
        borderColor: withAlpha(color, 0.35),
      }}
    >
      <Ionicons name="swap-horizontal" size={size * 0.5} color={color} />
    </View>
  );
}

/** Two small lettered circles ("A" / "B") for the anonymous community teams. */
export function AnonymousTeamPair({ color }: { color: string }) {
  const { colors } = useThemeMode();
  const dot = (letter: string, offset: boolean) => (
    <View
      style={[
        styles.dot,
        {
          marginLeft: offset ? -8 : 0,
          backgroundColor: withAlpha(color, 0.18),
          borderColor: withAlpha(color, 0.45),
        },
      ]}
    >
      <AppText style={[styles.dotText, { color: color || colors.textPrimary }]}>{letter}</AppText>
    </View>
  );
  return (
    <View style={styles.pair}>
      {dot('A', false)}
      {dot('B', true)}
    </View>
  );
}

/** Centered bar: fills right (success) for a positive net %, left (danger) for negative. */
export function NetEdgeBar({
  netPct,
  leftLabel,
  rightLabel,
}: {
  netPct: number;
  leftLabel?: string;
  rightLabel?: string;
}) {
  const { colors } = useThemeMode();
  const clamped = Math.max(-50, Math.min(50, netPct));
  const fill = netPct > 0 ? colors.success : netPct < 0 ? colors.danger : colors.textTertiary;
  const width = `${Math.abs(clamped)}%` as `${number}%`;
  const left = `${clamped >= 0 ? 50 : 50 - Math.abs(clamped)}%` as `${number}%`;
  return (
    <View
      style={styles.barWrap}
      accessible
      accessibilityLabel={`Value trend edge ${netPct > 0 ? '+' : ''}${netPct.toFixed(0)} percent`}
    >
      <View style={[styles.track, { backgroundColor: colors.border }]}>
        <View style={[styles.fill, { backgroundColor: fill, width, left }]} />
        <View style={[styles.mid, { backgroundColor: colors.borderStrong }]} />
      </View>
      {leftLabel || rightLabel ? (
        <View style={styles.labels}>
          <AppText style={[styles.label, { color: colors.textTertiary }]}>{leftLabel}</AppText>
          <AppText style={[styles.label, { color: colors.textTertiary }]}>{rightLabel}</AppText>
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  pair: { flexDirection: 'row', alignItems: 'center' },
  dot: { width: 28, height: 28, borderRadius: 14, borderWidth: 1, alignItems: 'center', justifyContent: 'center' },
  dotText: { fontSize: 12, fontWeight: '800' },
  barWrap: { gap: spacing.xs },
  track: { height: 6, borderRadius: radii.pill, overflow: 'hidden' },
  fill: { position: 'absolute', top: 0, bottom: 0 },
  mid: { position: 'absolute', top: 0, bottom: 0, left: '50%', width: 2, marginLeft: -1 },
  labels: { flexDirection: 'row', justifyContent: 'space-between' },
  label: { fontSize: 11 },
});
