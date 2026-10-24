import React, { useMemo } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import AccentCard from './AccentCard';
import AppText from './AppText';
import Button from './Button';
import SectionHeading from './SectionHeading';
import SkeletonBlock from './SkeletonBlock';
import ToneBadge from './ToneBadge';
import { useThemeMode } from '../context/ThemeModeContext';
import type { DashboardItem, ThisWeek, ThisWeekRow } from '../lib/api';
import { thisWeekTarget, thisWeekToneKey } from '../lib/thisWeek';
import { buildTodayPlan, todayTitle } from '../lib/todayPlan';
import { spacing, type ThemeColors } from '../theme';

/**
 * The Dashboard's one hero module: "Today" (mirrors web-next's TodayModule).
 * It merges the former "This week" strip and "Today" list into one
 * schedule-aware order (lib/todayPlan.ts): what matters today first (a risk
 * lineup row, top-priority cards, today's rows), then a quiet "Later this
 * week" list. Items that used to appear in both are shown once.
 */
export default function TodayHero({
  thisWeek,
  items = [],
  leagueId,
  leagueName,
  onNavigate,
  renderCard,
  right,
  empty,
  tradePending = false,
  now,
}: {
  thisWeek: ThisWeek | null | undefined;
  /** Raw dashboard items; only top_priority ones are used. */
  items?: DashboardItem[];
  leagueId: string;
  leagueName: string;
  onNavigate: (name: string, params: object) => void;
  /** The screen's rich top-priority card (trade card, briefing card). */
  renderCard?: (item: DashboardItem, index: number) => React.ReactNode;
  /** Title-row slot (View All link). */
  right?: React.ReactNode;
  /** Shown only when there is nothing real at all. */
  empty?: React.ReactNode;
  /** The progressive first Dashboard pass has no trade verdict yet: reserve
   * the trade row's space so the full response fills it without a layout jump. */
  tradePending?: boolean;
  now?: Date;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const plan = buildTodayPlan(thisWeek, items, now);
  if (plan.isEmpty && !empty) return null;
  const go = (route: Parameters<typeof thisWeekTarget>[0]) => {
    const target = thisWeekTarget(route, leagueId, leagueName);
    onNavigate(target.name, target.params);
  };
  const next = plan.nextAction;

  const renderRows = (rows: ThisWeekRow[]) =>
    rows.map((row, index) => {
      const color = colors[thisWeekToneKey(row.tone)];
      const actionable = Boolean(row.cta_label && row.route);
      const content = (
        <>
          <ToneBadge label={row.status} color={color} />
          <View style={styles.rowText}>
            <AppText style={styles.headline} numberOfLines={1}>
              {row.headline}
            </AppText>
            <AppText style={styles.why} numberOfLines={2}>
              {row.why}
            </AppText>
          </View>
          {actionable ? <AppText style={styles.arrow}>→</AppText> : null}
        </>
      );
      return actionable ? (
        <Pressable
          key={row.key}
          accessibilityRole="button"
          accessibilityLabel={row.cta_label ?? undefined}
          onPress={() => go(row.route!)}
          style={[styles.row, index > 0 ? styles.rowDivider : null]}
        >
          {content}
        </Pressable>
      ) : (
        <View key={row.key} style={[styles.row, index > 0 ? styles.rowDivider : null]}>
          {content}
        </View>
      );
    });

  // Consecutive rows share one card; a top-priority card stands on its own.
  const blocks: React.ReactNode[] = [];
  let pending: ThisWeekRow[] = [];
  const flush = () => {
    if (pending.length === 0) return;
    blocks.push(
      <AccentCard key={`rows-${blocks.length}`} accent={colors.accent} compact>
        {renderRows(pending)}
      </AccentCard>,
    );
    pending = [];
  };
  let cardIndex = 0;
  for (const entry of plan.today) {
    if (entry.kind === 'row') {
      pending.push(entry.row);
    } else {
      flush();
      blocks.push(<React.Fragment key={`card-${cardIndex}`}>{renderCard?.(entry.item, cardIndex)}</React.Fragment>);
      cardIndex += 1;
    }
  }
  flush();

  const showTradeSkeleton = tradePending && !next && !thisWeek?.rows.some((row) => row.key === 'trade');

  return (
    <View style={styles.wrap}>
      <SectionHeading title={todayTitle(thisWeek)} right={right} />
      {next ? (
        <AccentCard accent={colors.accent} compact>
          <AppText style={styles.headline}>{next.headline}</AppText>
          <AppText style={styles.why}>{next.why}</AppText>
          <Button label={next.cta_label} onPress={() => go(next.route)} style={styles.cta} />
        </AccentCard>
      ) : null}
      {blocks}
      {plan.later.length > 0 ? (
        <View>
          <AppText style={styles.laterLabel}>Later this week</AppText>
          {renderRows(plan.later)}
        </View>
      ) : null}
      {showTradeSkeleton ? <SkeletonBlock height={64} radius={12} /> : null}
      {plan.isEmpty ? empty : null}
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    wrap: { gap: spacing.sm },
    headline: { fontSize: 14, fontWeight: '700', color: colors.textPrimary },
    why: { fontSize: 13, color: colors.textSecondary },
    cta: { alignSelf: 'flex-start', paddingVertical: spacing.sm },
    row: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, minHeight: 44, paddingVertical: spacing.sm },
    rowDivider: { borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.border },
    rowText: { flex: 1, minWidth: 0 },
    arrow: { fontSize: 16, color: colors.accent },
    laterLabel: {
      fontSize: 11,
      fontWeight: '700',
      letterSpacing: 0.5,
      textTransform: 'uppercase',
      color: colors.textTertiary,
    },
  });
}
