import { openInsight } from '../lib/insightNav';
import type { InsightKey } from '../lib/insightLinks';
import React, { useMemo } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import AccentCard from './AccentCard';
import AppText from './AppText';
import BeginnerHelp from './BeginnerHelp';
import CompactModule from './CompactModule';
import { type StatStripItem } from './DashboardStatRow';
import { LinkModule, StatStripModule } from './ModuleTemplates';
import GlossaryNote from './GlossaryNote';
import ToneBadge from './ToneBadge';
import SectionHeading from './SectionHeading';
import { useThemeMode } from '../context/ThemeModeContext';
import type { DashboardItem, DashboardResponse, TeamRanking, TeamSnapshot } from '../lib/api';
import { useExperienceCopy } from '../context/ExperienceLevelContext';
import { formatRank } from '../lib/percentile';
import { leagueAverageAge } from '../lib/teamStatus';
import {
  deadlineChip,
  tradeIdeasLine,
  tradesGoalLine,
  TRADES_BLOCK_COPY,
  type DashboardAttentionEntry,
} from '../lib/dashboardLayout';
import { radii, spacing, type ThemeColors } from '../theme';

type Navigate = (name: string, params?: object) => void;

const ATTENTION_ROUTE: Record<string, string> = {
  trade_hub: 'Trades',
  waivers: 'Waivers',
  my_team: 'MyTeam',
};

/** Which screen a "Needs attention" entry opens (shared by the card and the status header's player rows). */
export function attentionEntryRoute(entry: DashboardAttentionEntry<DashboardItem>): string {
  if (entry.target === 'matchup') return 'Matchup';
  if (entry.target === 'gm_plan' || !entry.item) return 'GmPlan';
  return ATTENTION_ROUTE[entry.item.destination] ?? 'GmPlan';
}

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
  const routeFor = attentionEntryRoute;
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
            <View style={styles.attentionBadge}>
              <ToneBadge label={entry.badge} color={colors.danger} size="xs" />
            </View>
            <View style={styles.attentionText}>
              <AppText style={styles.holdHeadline} numberOfLines={2}>
                {entry.headline}
              </AppText>
              <AppText style={styles.holdWhy} numberOfLines={2}>
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
  deadlineInAttention = false,
  onNavigate,
}: {
  data: DashboardResponse;
  tradeItems: DashboardItem[];
  leagueId: string;
  leagueName: string;
  isBeginner: boolean;
  goal: string | null | undefined;
  /** "Needs attention" already lists a near deadline: don't repeat it here. */
  deadlineInAttention?: boolean;
  onNavigate: Navigate;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const deadlinePassed = Boolean(data.trade_window?.trade_deadline_passed);
  const pending = Boolean(data.trade_ideas_deferred) && tradeItems.length === 0;
  const goalLine = isBeginner ? tradesGoalLine(goal) : '';
  // The one home for the deadline: here, not also as a chip.
  const deadline = deadlineInAttention ? null : deadlineChip(data.trade_window);
  const stateTone = deadlinePassed || tradeItems.length === 0 ? ('muted' as const) : ('action' as const);
  return (
    <View style={styles.block}>
      <LinkModule
        title={TRADES_BLOCK_COPY.title}
        tone="action"
        onPress={() => onNavigate('Trades', { leagueId, leagueName })}
        parts={[
          { key: 'ideas', text: tradeIdeasLine(tradeItems.length, deadlinePassed, pending), tone: stateTone, strong: tradeItems.length > 0 && !deadlinePassed },
          deadline ? { key: 'deadline', text: `Deadline ${deadline.value}`, tone: deadline.tone === 'risk' ? ('danger' as const) : ('muted' as const) } : null,
          { key: 'link', text: TRADES_BLOCK_COPY.link, tone: 'accent' as const },
        ]}
      />
      {isBeginner ? (
        <BeginnerHelp text={`${TRADES_BLOCK_COPY.beginnerExplainer}${goalLine ? ` ${goalLine}` : ''}`} />
      ) : null}
    </View>
  );
}

/**
 * My Team on the Dashboard: the league ranks and roster-health facts the
 * "Your team right now" hero does not carry (record, standing and odds live
 * there). Each tile adds context only when the data exists: team count and
 * league-average age come from the team-rankings response. Mirrors web
 * DashboardContent buildTeamStats.
 */
export function DashboardTeamStats({
  snapshot,
  teams,
  leagueId,
  leagueName,
  onNavigate,
  onOpen,
}: {
  snapshot: TeamSnapshot;
  teams: TeamRanking[] | null;
  leagueId: string;
  leagueName: string;
  onNavigate: Navigate;
  /** Trailing "Open ›" link to the My Team screen. */
  onOpen?: () => void;
}) {
  const { colors } = useThemeMode();
  const copy = useExperienceCopy();
  const open = (key: InsightKey) => openInsight(onNavigate, key, leagueId, leagueName);
  const injured = snapshot.injured_starters != null && snapshot.injured_starters > 0 ? snapshot.injured_starters : 0;
  const ofTeams = teams && teams.length > 1 ? `of ${teams.length} teams` : null;
  const leagueAge = leagueAverageAge(teams);
  const rank = (label: string, icon: StatStripItem['icon'], value: number | null | undefined, tied: boolean, onPress: () => void): StatStripItem => ({
    label,
    icon,
    value: value != null ? formatRank(value, tied) : '—',
    note: value != null ? ofTeams : null,
    onPress,
  });
  const items: StatStripItem[] = [
    rank('Power Rank', 'trophy-outline', snapshot.power_rank, !!snapshot.power_rank_tied, open('power')),
    rank('Franchise Rank', 'shield-outline', snapshot.franchise_rank, !!snapshot.franchise_rank_tied, open('franchise')),
    rank('Starter Strength', 'link-outline', snapshot.starter_rank, !!snapshot.starter_rank_tied, open('starter')),
    rank('Bench Strength', 'layers-outline', snapshot.bench_rank, !!snapshot.bench_rank_tied, open('bench')),
    {
      label: copy.label('averageAge', 'Avg Age'),
      icon: 'hourglass-outline',
      value: snapshot.average_age != null ? snapshot.average_age.toFixed(1) : '—',
      note: snapshot.average_age != null && leagueAge ? `League avg ${leagueAge}` : null,
      onPress: open('age'),
    },
    {
      label: 'Injured starters',
      icon: 'medkit-outline',
      value: injured > 0 ? String(injured) : 'None',
      tone: injured > 0 ? 'risk' : 'positive',
      onPress: open('injury'),
    },
  ];
  return (
    <StatStripModule
      id="today.team"
      title="My Team"
      items={items}
      action={onOpen ? (
        <Pressable accessibilityRole="link" accessibilityLabel="Open My Team" onPress={onOpen} hitSlop={8} style={{ minHeight: 44, justifyContent: 'center' }}>
          <AppText style={{ fontWeight: '700', color: colors.accent }}>Open ›</AppText>
        </Pressable>
      ) : undefined}
      footer={<GlossaryNote terms={['powerRank', 'franchiseRank', 'averageAge', 'starterStrength', 'benchStrength']} />}
    />
  );
}

/** Secondary modules (league activity, mini-games, league type): one compact module, mounted only when opened. */
export function DashboardMore({ children }: { children: React.ReactNode }) {
  return (
    <CompactModule
      id="today.more"
      title="More"
      testID="dashboard-more"
      tone="muted"
      parts={[
        { key: 'a', text: 'League activity' },
        { key: 'g', text: '2 mini-games' },
        { key: 't', text: 'League type' },
      ]}
    >
      {children}
    </CompactModule>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    block: { gap: spacing.md },
    attentionRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, minHeight: 44, paddingVertical: spacing.sm },
    attentionDivider: { borderTopWidth: 1, borderTopColor: colors.border },
    attentionBadge: { width: 88, alignItems: 'flex-start' },
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
    tradeLineTextGroup: { flex: 1, paddingVertical: spacing.sm },
    deadlineNote: { fontSize: 13.5, color: colors.textTertiary },
    tradeLineText: { fontSize: 15.5, fontWeight: '700', color: colors.textPrimary },
    holdHeadline: { flexShrink: 1, fontSize: 15.5, fontWeight: '700', color: colors.textPrimary },
    holdWhy: { fontSize: 13.5, color: colors.textSecondary },
    link: { fontSize: 15.5, fontWeight: '700', color: colors.accent },
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
    moreHint: { flex: 1, textAlign: 'right', marginRight: spacing.sm, fontSize: 12.5, color: colors.textTertiary },
    moreTitle: { fontSize: 14.5, fontWeight: '700', letterSpacing: 0.5, color: colors.textPrimary },
    moreBody: { gap: spacing.lg, paddingTop: spacing.md },
  });
}
