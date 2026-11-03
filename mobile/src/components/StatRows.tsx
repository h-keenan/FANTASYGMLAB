import React, { useMemo, useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import AppText from './AppText';
import { useThemeMode } from '../context/ThemeModeContext';
import { ordinal, percentileColor } from '../lib/percentile';
import { COLLAPSE_AFTER, type StatRowModel } from '../lib/statRows';
import { radii, spacing, type ThemeColors } from '../theme';

export type ExploreHandler = (target: { key: string; label: string }) => void;

/**
 * One stat as a row: label and value on top, a thin percentile bar with its
 * ordinal under it, an optional trend line. Tapping opens the Percentile
 * Explorer (via `onExplore`) when the row has an explorer key. Mobile twin of
 * web-next's StatRows.tsx; the pool/season caption lives on the card header.
 */
export function StatRow({ row, onExplore, first }: { row: StatRowModel; onExplore?: ExploreHandler; first?: boolean }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const tint = row.percentile != null ? percentileColor(Math.max(0, Math.min(100, row.percentile)), colors) : colors.textTertiary;
  const trendColor =
    row.trendDirection === 'up' ? colors.success : row.trendDirection === 'down' ? colors.danger : colors.textTertiary;
  const tappable = Boolean(row.explorerKey && onExplore);
  const body = (
    <View style={[styles.row, !first && styles.rowBorder]}>
      <View style={styles.top}>
        <AppText style={styles.label}>{row.label}</AppText>
        <AppText style={styles.value}>{row.value || '—'}</AppText>
      </View>
      {row.percentile != null ? (
        <View style={styles.barLine}>
          <View style={styles.track}>
            <View style={[styles.fill, { width: `${Math.max(2, Math.min(100, row.percentile))}%`, backgroundColor: tint }]} />
          </View>
          <AppText style={[styles.pct, { color: tint }]}>{ordinal(row.percentile)}</AppText>
        </View>
      ) : null}
      {row.trend ? <AppText style={[styles.trend, { color: trendColor }]}>{row.trend}</AppText> : null}
    </View>
  );
  return tappable ? (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={`${row.label} percentile explorer`}
      onPress={() => onExplore!({ key: row.explorerKey as string, label: row.label })}
    >
      {body}
    </Pressable>
  ) : (
    body
  );
}

/** A card of rows; long lists show the first few and a "Show all" toggle. */
export function StatRowsCard({
  title,
  caption,
  rows,
  onExplore,
  collapseAfter = COLLAPSE_AFTER,
  children,
}: {
  title: string;
  caption?: string | null;
  rows: StatRowModel[];
  onExplore?: ExploreHandler;
  collapseAfter?: number;
  children?: React.ReactNode;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [expanded, setExpanded] = useState(false);
  if (rows.length === 0 && !children) return null;
  const shown = expanded ? rows : rows.slice(0, collapseAfter);
  return (
    <View style={styles.card}>
      <View style={styles.head}>
        <AppText style={styles.title}>{title.toUpperCase()}</AppText>
        {caption ? <AppText style={styles.caption}>{caption}</AppText> : null}
      </View>
      {children}
      {shown.map((row, index) => (
        <StatRow key={row.key} row={row} onExplore={onExplore} first={index === 0} />
      ))}
      {rows.length > collapseAfter ? (
        <Pressable accessibilityRole="button" onPress={() => setExpanded((value) => !value)}>
          <AppText style={styles.more}>{expanded ? 'Show fewer' : `Show all ${rows.length}`}</AppText>
        </Pressable>
      ) : null}
    </View>
  );
}

/** The few numbers that matter, large, at the top. */
export function HeadlineTiles({ rows, onExplore }: { rows: StatRowModel[]; onExplore?: ExploreHandler }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  if (rows.length === 0) return null;
  return (
    <View style={styles.strip}>
      {rows.map((row) => {
        const tint = row.percentile != null ? percentileColor(Math.max(0, Math.min(100, row.percentile)), colors) : colors.textTertiary;
        const tile = (
          <View style={styles.tile}>
            <AppText style={styles.tileLabel} numberOfLines={2}>{row.label.toUpperCase()}</AppText>
            <AppText style={styles.tileValue}>{row.value}</AppText>
            {row.percentile != null ? <AppText style={[styles.tilePct, { color: tint }]}>{ordinal(row.percentile)} pct</AppText> : null}
          </View>
        );
        return row.explorerKey && onExplore ? (
          <Pressable
            key={row.key}
            style={styles.tileWrap}
            accessibilityRole="button"
            accessibilityLabel={`${row.label} percentile explorer`}
            onPress={() => onExplore({ key: row.explorerKey as string, label: row.label })}
          >
            {tile}
          </Pressable>
        ) : (
          <View key={row.key} style={styles.tileWrap}>{tile}</View>
        );
      })}
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    card: {
      padding: spacing.md,
      borderRadius: radii.md,
      borderWidth: StyleSheet.hairlineWidth * 1.5,
      borderColor: colors.glassBorder,
      backgroundColor: colors.glass,
      marginBottom: spacing.md,
    },
    head: { flexDirection: 'row', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: spacing.xs },
    title: { fontSize: 11, fontWeight: '800', letterSpacing: 1, color: colors.textTertiary },
    caption: { fontSize: 11, color: colors.textTertiary },
    row: { paddingVertical: spacing.sm, gap: 4 },
    rowBorder: { borderTopWidth: StyleSheet.hairlineWidth * 1.5, borderTopColor: colors.glassBorder },
    top: { flexDirection: 'row', alignItems: 'baseline', justifyContent: 'space-between' },
    label: { fontSize: 14, fontWeight: '600', color: colors.textSecondary },
    value: { fontSize: 17, fontWeight: '800', color: colors.textPrimary },
    barLine: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
    track: { flex: 1, height: 6, borderRadius: radii.pill, backgroundColor: colors.backgroundElevated, overflow: 'hidden' },
    fill: { height: '100%', borderRadius: radii.pill },
    pct: { minWidth: 38, textAlign: 'right', fontSize: 12, fontWeight: '700' },
    trend: { fontSize: 12 },
    more: { fontSize: 13, fontWeight: '700', color: colors.accent, paddingTop: spacing.xs },
    strip: { flexDirection: 'row', gap: spacing.sm, marginBottom: spacing.md },
    tileWrap: { flex: 1 },
    tile: {
      flex: 1,
      padding: spacing.sm,
      borderRadius: radii.md,
      borderWidth: StyleSheet.hairlineWidth * 1.5,
      borderColor: colors.glassBorder,
      backgroundColor: colors.glass,
      gap: 2,
    },
    tileLabel: { fontSize: 10, fontWeight: '700', letterSpacing: 0.6, color: colors.textTertiary },
    tileValue: { fontSize: 24, fontWeight: '800', color: colors.textPrimary },
    tilePct: { fontSize: 12, fontWeight: '700' },
  });
}
