import React, { useMemo } from 'react';
import { StyleSheet, View } from 'react-native';

import AppText from './AppText';
import ToneBadge from './ToneBadge';
import { useThemeMode } from '../context/ThemeModeContext';
import { RANGE_CAPTION, formatPoints, leanLabel, type RangeDisplayRow } from '../lib/startSitRange';
import { spacing, type ThemeColors } from '../theme';

/**
 * Projected / Low / High for the compared players side by side, with the
 * win-probability lean (Ceiling play / Floor play) and its plain-English why
 * when the matchup stance calls for one. Low and High are a typical-week range,
 * so the caption says exactly that. Renders nothing when no side has a real
 * range. Mirrors web-next/src/components/RangeCompare.tsx.
 */
export default function RangeCompare({
  rows,
  lean,
  hideCaption = false,
  hideLean = false,
}: {
  rows: RangeDisplayRow[];
  lean: { kind: 'ceiling' | 'floor'; why: string } | null;
  /** A list of cards shows the caption once instead of on every card. */
  hideCaption?: boolean;
  /** The caller renders the lean note itself. */
  hideLean?: boolean;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  if (rows.length === 0) return null;
  return (
    <View style={styles.wrap} testID="range-compare">
      <View style={styles.row}>
        <View style={styles.nameCol} />
        {['Proj', 'Low', 'High'].map((label) => (
          <AppText key={label} style={[styles.num, styles.head]}>
            {label}
          </AppText>
        ))}
      </View>
      {rows.map((row) => (
        <View key={row.key} style={[styles.row, styles.dataRow, row.favored && { borderLeftColor: colors.accent }]}>
          <AppText style={styles.nameCol} numberOfLines={2}>
            <AppText style={styles.label}>{row.label} </AppText>
            <AppText style={styles.name}>{row.name || 'Player'}</AppText>
          </AppText>
          <AppText style={[styles.num, styles.proj]} accessibilityLabel={`Projected ${formatPoints(row.range.projected)}`}>
            {formatPoints(row.range.projected)}
          </AppText>
          <AppText style={styles.num} accessibilityLabel={`Low ${formatPoints(row.range.low)}`}>
            {formatPoints(row.range.low)}
          </AppText>
          <AppText style={styles.num} accessibilityLabel={`High ${formatPoints(row.range.high)}`}>
            {formatPoints(row.range.high)}
          </AppText>
        </View>
      ))}
      {lean && !hideLean ? (
        <View style={styles.lean} testID="range-lean">
          <ToneBadge label={leanLabel(lean.kind)} color={colors.accent} />
          <AppText style={styles.why}>{lean.why}</AppText>
        </View>
      ) : null}
      {hideCaption ? null : <AppText style={styles.caption}>{RANGE_CAPTION}</AppText>}
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    wrap: { gap: 6, alignSelf: 'stretch' },
    row: { flexDirection: 'row', alignItems: 'baseline', gap: spacing.sm },
    dataRow: { borderLeftWidth: 3, borderLeftColor: 'transparent', paddingLeft: spacing.sm },
    nameCol: { flex: 1, minWidth: 0 },
    num: { width: 44, textAlign: 'right', fontSize: 13, color: colors.textPrimary },
    head: { fontSize: 10, fontWeight: '800', textTransform: 'uppercase', color: colors.textTertiary },
    proj: { fontWeight: '700' },
    label: { fontSize: 11, color: colors.textTertiary },
    name: { fontSize: 13, fontWeight: '700', color: colors.textPrimary },
    lean: { gap: 4, alignItems: 'flex-start' },
    why: { fontSize: 12, color: colors.textSecondary },
    caption: { fontSize: 11, color: colors.textTertiary },
  });
}
