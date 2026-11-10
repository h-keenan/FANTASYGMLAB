import React, { useMemo, useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import AccentCard from './AccentCard';
import AppText from './AppText';
import BeginnerHelp from './BeginnerHelp';
import DashboardStatRow, { type StatStripItem } from './DashboardStatRow';
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
        <View style={styles.tradeLineTextGroup}>
          <AppText style={styles.tradeLineText} numberOfLines={2}>
            {tradeIdeasLine(tradeItems.length, deadlinePassed, pending)}
          </AppText>
          {deadline ? (
            <AppText style={[styles.deadlineNote, deadline.tone === 'risk' && { color: colors.danger }]} numberOfLines={1}>
              Trade deadline: {deadline.value}
            </AppText>
          ) : null}
        </View>
        <AppText style={styles.link} numberOfLines={1}>{TRADES_BLOCK_COPY.link} ›</AppText>
      </Pressable>
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
}: {
  snapshot: TeamSnapshot;
  teams: TeamRanking[] | null;
  leagueId: string;
  leagueName: string;
  onNavigate: Navigate;
}) {
  const copy = useExperienceCopy();
  const goToTeams = () => onNavigate('Teams', { leagueId, leagueName });
  const injured = snapshot.injured_starters != null && snapshot.injured_starters > 0 ? snapshot.injured_starters : 0;
  const ofTeams = teams && teams.length > 1 ? `of ${teams.length} teams` : null;
  const leagueAge = leagueAverageAge(teams);
  const rank = (label: string, icon: StatStripItem['icon'], value: number | null | undefined, tied: boolean, onPress?: () => void): StatStripItem => ({
    label,
    icon,
    value: value != null ? formatRank(value, tied) : '—',
    note: value != null ? ofTeams : null,
    onPress,
  });
  const items: StatStripItem[] = [
    rank('Power Rank', 'trophy-outline', snapshot.power_rank, !!snapshot.power_rank_tied, goToTeams),
    rank('Franchise Rank', 'shield-outline', snapshot.franchise_rank, !!snapshot.franchise_rank_tied, goToTeams),
    rank('Starter Strength', 'link-outline', snapshot.starter_rank, !!snapshot.starter_rank_tied),
    rank('Bench Strength', 'layers-outline', snapshot.bench_rank, !!snapshot.bench_rank_tied),
    {
      label: copy.label('averageAge', 'Avg Age'),
      icon: 'hourglass-outline',
      value: snapshot.average_age != null ? snapshot.average_age.toFixed(1) : '—',
      note: snapshot.average_age != null && leagueAge ? `League avg ${leagueAge}` : null,
    },
    {
      label: 'Injured starters',
      icon: 'medkit-outline',
      value: injured > 0 ? String(injured) : 'None',
      tone: injured > 0 ? 'risk' : 'positive',
    },
  ];
  return (
    <View>
      <DashboardStatRow items={items.slice(0, 3)} />
      <DashboardStatRow items={items.slice(3)} />
      <GlossaryNote terms={['powerRank', 'franchiseRank', 'averageAge', 'starterStrength', 'benchStrength']} />
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
        <AppText style={styles.moreHint} numberOfLines={1}>League activity, games, settings</AppText>
        <Ionicons name={open ? 'chevron-up' : 'chevron-down'} size={16} color={colors.textSecondary} />
      </Pressable>
      {open ? <View style={styles.moreBody}>{children}</View> : null}
    </View>
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
    deadlineNote: { fontSize: 12, color: colors.textTertiary },
    tradeLineText: { fontSize: 14, fontWeight: '700', color: colors.textPrimary },
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
    moreBody: { gap: spacing.lg, paddingTop: spacing.md },
  });
}
