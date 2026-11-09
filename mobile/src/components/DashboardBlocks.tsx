import React, { useMemo, useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import AccentCard from './AccentCard';
import AppText from './AppText';
import BeginnerHelp from './BeginnerHelp';
import ToneBadge from './ToneBadge';
import SectionHeading from './SectionHeading';
import { useThemeMode } from '../context/ThemeModeContext';
import type { DashboardItem, DashboardResponse } from '../lib/api';
import {
  buildNowChips,
  tradeIdeasLine,
  tradesGoalLine,
  TRADES_BLOCK_COPY,
  type DashboardAttentionEntry,
  type DashboardNowChip,
} from '../lib/dashboardLayout';
import { radii, spacing, type ThemeColors } from '../theme';

type Navigate = (name: string, params?: object) => void;

const CHIP_TARGET: Record<DashboardNowChip['route'], string> = {
  matchup: 'Matchup',
  trade_hub: 'Trades',
  alerts: 'Alerts',
  waivers: 'Waivers',
};

/** "At a glance": real status chips (lineup, trade deadline, alerts, waivers). Mirrors web DashboardNowStrip. */
export function DashboardNowStrip({
  data,
  leagueId,
  leagueName,
  onNavigate,
  exclude,
}: {
  data: DashboardResponse;
  leagueId: string;
  leagueName: string;
  onNavigate: Navigate;
  /** Chip keys already listed under "Needs attention". */
  exclude?: readonly string[];
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const alertCount = data.items.filter((item) => item.category !== 'top_priority').length;
  const chips = buildNowChips(data.this_week?.rows, data.trade_window, alertCount, exclude);
  if (chips.length === 0) return null;
  const tone: Record<DashboardNowChip['tone'], string> = {
    positive: colors.success,
    risk: colors.danger,
    waiver: colors.accent,
    neutral: colors.textPrimary,
  };
  return (
    <View style={styles.chipGrid} accessibilityLabel="At a glance">
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

const ATTENTION_ROUTE: Record<string, string> = {
  trade_hub: 'Trades',
  waivers: 'Waivers',
  my_team: 'MyTeam',
};

/**
 * "Needs attention": the few urgent items, one line each, each opening where it
 * is handled. Urgency is read only from existing fields
 * (lib/dashboardLayout.ts buildNeedsAttention). Mirrors web DashboardNeedsAttention.
 */
export function DashboardNeedsAttention({
  entries,
  leagueId,
  leagueName,
  onNavigate,
}: {
  entries: DashboardAttentionEntry<DashboardItem>[];
  leagueId: string;
  leagueName: string;
  onNavigate: Navigate;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  if (entries.length === 0) return null;
  const routeFor = (entry: DashboardAttentionEntry<DashboardItem>): string => {
    if (entry.target === 'matchup') return 'Matchup';
    if (entry.target === 'gm_plan' || !entry.item) return 'GmPlan';
    return ATTENTION_ROUTE[entry.item.destination] ?? 'GmPlan';
  };
  return (
    <View style={styles.block}>
      <SectionHeading title="Needs attention" />
      <AccentCard accent={colors.danger} compact>
        {entries.map((entry, index) => (
          <Pressable
            key={`${entry.source}-${index}`}
            accessibilityRole="button"
            accessibilityLabel={`${entry.headline}. ${entry.why}`}
            onPress={() => onNavigate(routeFor(entry), { leagueId, leagueName })}
            style={[styles.attentionRow, index > 0 && styles.attentionDivider]}
          >
            <ToneBadge label={entry.badge} color={colors.danger} size="xs" />
            <View style={styles.attentionText}>
              <AppText style={styles.holdHeadline} numberOfLines={1}>
                {entry.headline}
              </AppText>
              <AppText style={styles.holdWhy} numberOfLines={1}>
                {entry.why}
              </AppText>
            </View>
            <Ionicons name="chevron-forward" size={16} color={colors.accent} />
          </Pressable>
        ))}
      </AccentCard>
    </View>
  );
}

/**
 * Trade ideas on the Dashboard are one line: a count and a link. The idea cards
 * live only on GM Plan and Trade Hub. Mirrors web DashboardTradesBlock.
 */
export function DashboardTradesBlock({
  data,
  tradeItems,
  leagueId,
  leagueName,
  isBeginner,
  goal,
  onNavigate,
}: {
  data: DashboardResponse;
  tradeItems: DashboardItem[];
  leagueId: string;
  leagueName: string;
  isBeginner: boolean;
  goal: string | null | undefined;
  onNavigate: Navigate;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const deadlinePassed = Boolean(data.trade_window?.trade_deadline_passed);
  const pending = Boolean(data.trade_ideas_deferred) && tradeItems.length === 0;
  const goalLine = isBeginner ? tradesGoalLine(goal) : '';
  return (
    <View style={styles.block}>
      <SectionHeading title={TRADES_BLOCK_COPY.title} />
      {isBeginner ? (
        <BeginnerHelp text={`${TRADES_BLOCK_COPY.beginnerExplainer}${goalLine ? ` ${goalLine}` : ''}`} />
      ) : null}
      <Pressable
        accessibilityRole="link"
        accessibilityLabel={`${tradeIdeasLine(tradeItems.length, deadlinePassed, pending)}. Open ${TRADES_BLOCK_COPY.link}`}
        onPress={() => onNavigate('Trades', { leagueId, leagueName })}
        style={styles.tradeLine}
      >
        <AppText style={styles.tradeLineText} numberOfLines={2}>
          {tradeIdeasLine(tradeItems.length, deadlinePassed, pending)}
        </AppText>
        <AppText style={styles.link}>{TRADES_BLOCK_COPY.link} ›</AppText>
      </Pressable>
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
        <AppText style={styles.moreHint}>League activity, games, settings</AppText>
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
    attentionRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, minHeight: 44, paddingVertical: spacing.sm },
    attentionDivider: { borderTopWidth: 1, borderTopColor: colors.border },
    attentionText: { flex: 1, minWidth: 0 },
    tradeLine: {
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent: 'space-between',
      gap: spacing.sm,
      minHeight: 44,
      paddingHorizontal: spacing.md,
      borderRadius: radii.md,
      borderWidth: 1,
      borderColor: colors.border,
      backgroundColor: colors.surface,
    },
    tradeLineText: { flex: 1, fontSize: 14, fontWeight: '700', color: colors.textPrimary },
    holdHeadline: { flexShrink: 1, fontSize: 14, fontWeight: '700', color: colors.textPrimary },
    holdWhy: { fontSize: 12, color: colors.textSecondary },
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
    moreHint: { flex: 1, textAlign: 'right', marginRight: spacing.sm, fontSize: 11, color: colors.textTertiary },
    moreTitle: { fontSize: 13, fontWeight: '700', letterSpacing: 0.5, color: colors.textPrimary },
    moreBody: { gap: spacing.md, paddingTop: spacing.md },
  });
}
