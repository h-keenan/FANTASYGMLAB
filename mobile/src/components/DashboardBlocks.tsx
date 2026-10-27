import React, { useMemo, useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import AppText from './AppText';
import BeginnerHelp from './BeginnerHelp';
import Button from './Button';
import SectionHeading from './SectionHeading';
import SkeletonBlock from './SkeletonBlock';
import { useThemeMode } from '../context/ThemeModeContext';
import type { DashboardItem, DashboardResponse } from '../lib/api';
import {
  buildNowChips,
  tradesGoalLine,
  TRADES_BLOCK_COPY,
  type DashboardNowChip,
} from '../lib/dashboardLayout';
import { LINK_HIT_SLOP, radii, spacing, type ThemeColors } from '../theme';

type Navigate = (name: string, params?: object) => void;

const CHIP_TARGET: Record<DashboardNowChip['route'], string> = {
  matchup: 'Matchup',
  trade_hub: 'Trades',
  alerts: 'Alerts',
  waivers: 'Waivers',
};

/** "What matters now": real status chips (lineup, trade deadline, alerts, waivers). Mirrors web DashboardNowStrip. */
export function DashboardNowStrip({
  data,
  leagueId,
  leagueName,
  onNavigate,
}: {
  data: DashboardResponse;
  leagueId: string;
  leagueName: string;
  onNavigate: Navigate;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const alertCount = data.items.filter((item) => item.category !== 'top_priority').length;
  const chips = buildNowChips(data.this_week?.rows, data.trade_window, alertCount);
  if (chips.length === 0) return null;
  const tone: Record<DashboardNowChip['tone'], string> = {
    positive: colors.success,
    risk: colors.danger,
    waiver: colors.accent,
    neutral: colors.textPrimary,
  };
  return (
    <View style={styles.chipGrid} accessibilityLabel="What matters now">
      {chips.map((chip) => (
        <Pressable
          key={chip.key}
          accessibilityRole="button"
          accessibilityLabel={`${chip.label}: ${chip.value}`}
          onPress={() => onNavigate(CHIP_TARGET[chip.route], { leagueId, leagueName })}
          style={styles.chip}
        >
          <AppText style={styles.chipLabel}>{chip.label.toUpperCase()}</AppText>
          <AppText style={[styles.chipValue, { color: tone[chip.tone] }]} numberOfLines={1}>
            {chip.value}
          </AppText>
        </Pressable>
      ))}
    </View>
  );
}

/**
 * The primary block: the best real trade idea, one primary action
 * ("Analyze a trade") and one quiet link to the rest of the board. Mirrors
 * web DashboardTradesBlock.
 */
export function DashboardTradesBlock({
  data,
  tradeItems,
  leagueId,
  leagueName,
  isBeginner,
  goal,
  onNavigate,
  renderTradeCard,
}: {
  data: DashboardResponse;
  tradeItems: DashboardItem[];
  leagueId: string;
  leagueName: string;
  isBeginner: boolean;
  goal: string | null | undefined;
  onNavigate: Navigate;
  renderTradeCard: (item: DashboardItem, index: number) => React.ReactNode;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const deadlinePassed = Boolean(data.trade_window?.trade_deadline_passed);
  const pending = Boolean(data.trade_ideas_deferred) && tradeItems.length === 0;
  const holdRow = data.this_week?.rows.find((row) => row.key === 'trade');
  const goalLine = isBeginner ? tradesGoalLine(goal) : '';
  return (
    <View style={styles.block}>
      <SectionHeading title={TRADES_BLOCK_COPY.title} />
      {isBeginner ? (
        <BeginnerHelp text={`${TRADES_BLOCK_COPY.beginnerExplainer}${goalLine ? ` ${goalLine}` : ''}`} />
      ) : null}
      {deadlinePassed ? (
        <AppText style={styles.bodyText}>{TRADES_BLOCK_COPY.deadlinePassed}</AppText>
      ) : tradeItems.length > 0 ? (
        tradeItems.slice(0, 3).map((item, index) => renderTradeCard(item, index))
      ) : pending ? (
        <SkeletonBlock height={96} radius={12} />
      ) : (
        <AppText style={styles.bodyText}>
          {holdRow ? `${holdRow.headline}. ${holdRow.why}` : TRADES_BLOCK_COPY.empty}
        </AppText>
      )}
      <View style={styles.actionRow}>
        <Button
          size="sm"
          label={TRADES_BLOCK_COPY.analyze}
          onPress={() => onNavigate('Trades', { leagueId, leagueName, initialTab: 'make' })}
        />
        {deadlinePassed ? null : (
          <Pressable
            accessibilityRole="link"
            hitSlop={LINK_HIT_SLOP}
            onPress={() => onNavigate('Trades', { leagueId, leagueName })}
          >
            <AppText style={styles.link}>{TRADES_BLOCK_COPY.more} ›</AppText>
          </Pressable>
        )}
      </View>
    </View>
  );
}

/** Secondary modules, collapsed by default. Mirrors web DashboardMore (<details>). */
export function DashboardMore({ children }: { children: React.ReactNode }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [open, setOpen] = useState(false);
  return (
    <View>
      <Pressable
        accessibilityRole="button"
        accessibilityState={{ expanded: open }}
        accessibilityLabel="More"
        onPress={() => setOpen((value) => !value)}
        style={styles.moreHeader}
      >
        <AppText style={styles.moreTitle}>MORE</AppText>
        <Ionicons name={open ? 'chevron-up' : 'chevron-down'} size={16} color={colors.textSecondary} />
      </Pressable>
      {open ? <View style={styles.moreBody}>{children}</View> : null}
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    chipGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
    chip: {
      flexBasis: '48%',
      flexGrow: 1,
      minHeight: 44,
      paddingHorizontal: spacing.md,
      paddingVertical: spacing.sm,
      borderRadius: radii.md,
      borderWidth: 1,
      borderColor: colors.border,
      backgroundColor: colors.surface,
    },
    chipLabel: { fontSize: 11, fontWeight: '700', letterSpacing: 0.5, color: colors.textTertiary },
    chipValue: { fontSize: 14, fontWeight: '700' },
    block: { gap: spacing.sm },
    bodyText: { fontSize: 14, color: colors.textSecondary },
    actionRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.md, flexWrap: 'wrap' },
    link: { fontSize: 14, fontWeight: '700', color: colors.accent },
    moreHeader: {
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent: 'space-between',
      minHeight: 44,
      paddingHorizontal: spacing.md,
      borderRadius: radii.md,
      borderWidth: 1,
      borderColor: colors.border,
      backgroundColor: colors.surface,
    },
    moreTitle: { fontSize: 13, fontWeight: '700', letterSpacing: 0.5, color: colors.textPrimary },
    moreBody: { gap: spacing.md, paddingTop: spacing.md },
  });
}
