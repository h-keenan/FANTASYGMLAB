import React, { useMemo } from 'react';
import { StyleSheet, TouchableOpacity, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import AppText from './AppText';
import PercentileBar from './PercentileBar';
import { useThemeMode } from '../context/ThemeModeContext';
import { percentileColor, percentileLabel, percentileTrendIcon } from '../lib/percentile';
import { radii, spacing, type ThemeColors } from '../theme';

/**
 * Compact 2-column stat card for the Stats tab's analytic groups (Fantasy
 * Scoring / Production / Receiving / Efficiency) — coridian_'s concept-sheet
 * replacement for the old equal-weight StatCell grid. Same real
 * label/value/percentile every StatCell already rendered, just denser and
 * with a percentile bar instead of relying on the caret+text alone to carry
 * "how good is this". Renders fine with no percentile (just label + value)
 * — that plain mode is also what Dashboard's League Snapshot uses for
 * rank/count metrics (record, power rank, injury count) that have no
 * percentile framing at all.
 */
export default function MetricCard({
  label,
  value,
  percentile,
  valueColor,
  onPress,
}: {
  label: string;
  value: string | number | null;
  percentile?: number | null;
  /** Overrides the value text color — for emphasizing an especially
   * important or abnormal reading (e.g. a non-zero injury count in
   * `colors.danger`) without a one-off card style just for that metric. */
  valueColor?: string;
  /** Makes the whole tile tappable (e.g. Dashboard's Power/Franchise rank
   * tiles, which drill into the Teams screen) while leaving every other
   * caller — anything that omits this — a plain, non-interactive View. */
  onPress?: () => void;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const display = value === null || value === undefined || value === '' ? '—' : value;
  const pctl = percentileLabel(percentile);
  const trendIcon = percentileTrendIcon(percentile);
  const content = (
    <>
      <AppText style={styles.label} numberOfLines={1}>
        {label}
      </AppText>
      <AppText style={[styles.value, valueColor ? { color: valueColor } : null]} numberOfLines={1}>
        {display}
      </AppText>
      {pctl && trendIcon ? (
        <View style={styles.pctlRow}>
          <Ionicons name={trendIcon} size={11} color={percentileColor(percentile, colors)} />
          <AppText style={[styles.pctlText, { color: percentileColor(percentile, colors) }]} numberOfLines={1}>
            {pctl}
          </AppText>
        </View>
      ) : null}
      <PercentileBar percentile={percentile} />
    </>
  );
  if (onPress) {
    return (
      <TouchableOpacity style={styles.card} onPress={onPress} activeOpacity={0.7}>
        {content}
      </TouchableOpacity>
    );
  }
  return <View style={styles.card}>{content}</View>;
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    card: {
      minWidth: '46%',
      flexGrow: 1,
      backgroundColor: colors.backgroundElevated,
      borderRadius: radii.sm,
      paddingHorizontal: spacing.md,
      paddingVertical: spacing.sm,
    },
    label: {
      fontSize: 10,
      color: colors.textSecondary,
      textTransform: 'uppercase',
      letterSpacing: 0.3,
      marginBottom: 3,
    },
    value: { fontSize: 18, fontWeight: '700', color: colors.textPrimary },
    pctlRow: { flexDirection: 'row', alignItems: 'center', gap: 2, marginTop: 3 },
    pctlText: { fontSize: 10, fontWeight: '600', letterSpacing: 0.2 },
  });
}
