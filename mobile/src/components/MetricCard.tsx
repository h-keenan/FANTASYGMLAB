import React, { useMemo } from 'react';
import { StyleProp, StyleSheet, TouchableOpacity, View, ViewStyle } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import AppText from './AppText';
import PercentileBar from './PercentileBar';
import { useThemeMode } from '../context/ThemeModeContext';
import { percentileColor, percentileLabel, percentileTrendIcon } from '../lib/percentile';
import { radii, spacing, type ThemeColors } from '../theme';

type IoniconName = React.ComponentProps<typeof Ionicons>['name'];

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
  icon,
  value,
  percentile,
  valueColor,
  note,
  periodLabel,
  onPress,
  style,
}: {
  label: string;
  /** Small glyph in front of the label (e.g. a trophy for Roster Power, a star for
   * Franchise) — coridian_'s ask for the Roster Analysis tiles to "pop"
   * instead of reading as plain text. Same leading-icon-before-title
   * pattern AnalyticsSection's header already uses, just scoped to one
   * tile's label instead of a whole card header. Optional so every other
   * MetricCard caller (Dashboard snapshot, PlayerDetail stat grids, etc.)
   * keeps its plain text-only label unchanged. */
  icon?: IoniconName;
  value: string | number | null;
  percentile?: number | null;
  /** Overrides the value text color — for emphasizing an especially
   * important or abnormal reading (e.g. a non-zero injury count in
   * `colors.danger`) without a one-off card style just for that metric. */
  valueColor?: string;
  /** Short qualitative caption shown under the value (e.g. "Prime",
   * "Aging") for a metric that has no percentile to render — omitted
   * whenever `percentile` produces a pctl row, so a tile never shows two
   * competing caption lines. Added for My Team's Roster Age tile, which
   * has a semantic age bucket but no rank-derived percentile. */
  note?: string | null;
  /** Tiny always-visible tag (e.g. "SEASON TOTAL", "PER GAME") next to the
   * label, for metrics that could otherwise be misread as the wrong kind of
   * number sitting right next to a sibling tile — coridian_'s Fantasy
   * Output ask: "PPR 48.3" next to "PPR PPG 16.1" doesn't say which one is
   * cumulative. Unlike `note`, this renders alongside the percentile row
   * rather than being replaced by it, since the whole point is it must
   * stay visible even when a percentile is present. */
  periodLabel?: string | null;
  /** Makes the whole tile tappable (e.g. Dashboard's Roster Power/Franchise rank
   * tiles, which drill into the Teams screen) while leaving every other
   * caller — anything that omits this — a plain, non-interactive View. */
  onPress?: () => void;
  /** Overrides the tile's own sizing (e.g. a fixed one-third `flexBasis`
   * for a caller that always renders exactly three tiles in one compact
   * row) without touching the default `minWidth: '46%'` two-up layout every
   * other caller relies on. Merged after the base card style. */
  style?: StyleProp<ViewStyle>;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const display = value === null || value === undefined || value === '' ? '—' : value;
  const pctl = percentileLabel(percentile);
  const trendIcon = percentileTrendIcon(percentile);
  const content = (
    <>
      <View style={styles.labelRow}>
        <View style={styles.labelTextRow}>
          {icon ? <Ionicons name={icon} size={11} color={colors.accent} style={styles.labelIcon} /> : null}
          <AppText style={styles.label} numberOfLines={1}>
            {label}
          </AppText>
        </View>
        {/* Same chevron-forward + textTertiary affordance InsightRow/
         * AwardsStrip/WaiverRecommendationCard already use to mark a row as
         * tappable — reused here rather than inventing a card-specific
         * tappability indicator, so every MetricCard with an `onPress`
         * (Dashboard's Roster Power/Franchise tiles included) now signals it the
         * same way the rest of the app does. */}
        {periodLabel ? (
          <View style={styles.periodTag}>
            <AppText style={styles.periodTagText} numberOfLines={1}>
              {periodLabel}
            </AppText>
          </View>
        ) : onPress ? (
          <Ionicons name="chevron-forward" size={12} color={colors.textTertiary} />
        ) : null}
      </View>
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
      ) : note ? (
        <AppText style={[styles.noteText, { color: valueColor ?? colors.textTertiary }]} numberOfLines={1}>
          {note}
        </AppText>
      ) : null}
      <PercentileBar percentile={percentile} />
    </>
  );
  if (onPress) {
    return (
      <TouchableOpacity style={[styles.card, style]} onPress={onPress} activeOpacity={0.7}>
        {content}
      </TouchableOpacity>
    );
  }
  return <View style={[styles.card, style]}>{content}</View>;
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
    labelRow: {
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent: 'space-between',
      gap: spacing.xs,
      marginBottom: 3,
    },
    labelTextRow: { flexDirection: 'row', alignItems: 'center', flexShrink: 1 },
    labelIcon: { marginRight: 4 },
    label: {
      flexShrink: 1,
      fontSize: 10,
      color: colors.textSecondary,
      textTransform: 'uppercase',
      letterSpacing: 0.3,
    },
    value: { fontSize: 18, fontWeight: '700', color: colors.textPrimary },
    pctlRow: { flexDirection: 'row', alignItems: 'center', gap: 2, marginTop: 3 },
    pctlText: { fontSize: 10, fontWeight: '600', letterSpacing: 0.2 },
    noteText: { fontSize: 10, fontWeight: '600', letterSpacing: 0.2, marginTop: 3 },
    // Neutral pill, deliberately quieter than the percentile/position
    // badges — it's disambiguating metadata ("is this a season total or a
    // per-game rate"), not a judgment on the number, so it borrows
    // `textTertiary` rather than any semantic color.
    periodTag: {
      borderRadius: radii.pill,
      backgroundColor: `${colors.textTertiary}26`,
      paddingHorizontal: 5,
      paddingVertical: 1,
    },
    periodTagText: {
      fontSize: 8,
      fontWeight: '700',
      letterSpacing: 0.3,
      color: colors.textTertiary,
      textTransform: 'uppercase',
    },
  });
}
