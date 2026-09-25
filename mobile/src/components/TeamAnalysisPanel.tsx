import React, { useMemo } from 'react';
import { StyleSheet, View } from 'react-native';

import AnalyticsSection from './AnalyticsSection';
import AppText from './AppText';
import InsightRow from './InsightRow';
import MetricCard from './MetricCard';
import { useThemeMode } from '../context/ThemeModeContext';
import type { TeamRanking } from '../lib/api';
import { percentileColor, percentileFromRank } from '../lib/percentile';
import { spacing, type ThemeColors } from '../theme';

/**
 * Shared "roster analysis" content: the full TeamRanking rank matrix
 * (Power/Franchise/Draft Capital/Starters/Bench/Age) plus the archetype
 * narrative (explanation, strengths, risks, recommendations) and real trade
 * behavior — every field here already exists on `TeamRanking`
 * (services/mobile_api_service.py via modules/team_eval.py +
 * modules/league_rankings.py), nothing computed or invented client-side.
 *
 * Extracted out for My Team's new Analysis tab (coridian_'s My Team
 * "roster command center" brief, section 15) rather than re-deriving this
 * from scratch — TeamRosterScreen's `TeamSnapshotSection`/
 * `ArchetypeDetailList` already render this exact same data (for a
 * league-mate's roster) with an equivalent but page-local, non-exported
 * implementation. That duplication predates this component; a follow-up
 * pass should migrate TeamRosterScreen onto this shared panel instead of
 * carrying two copies of the same rank-matrix + archetype-narrative layout.
 */
export default function TeamAnalysisPanel({
  team,
  leagueSize,
  onOpenTeams,
}: {
  team: TeamRanking;
  leagueSize: number;
  onOpenTeams?: () => void;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const metrics = useMemo(() => buildRankMetrics(team), [team]);
  const hasTradeContext = team.trade_tendency && team.trade_tendency !== 'Neutral';

  return (
    <AnalyticsSection title="Roster Analysis" icon="stats-chart-outline">
      {metrics.length > 0 ? (
        <View style={styles.metricsRow}>
          {metrics.map((metric) => {
            const percentile = percentileFromRank(metric.rank, leagueSize);
            return (
              <MetricCard
                key={metric.key}
                label={metric.label}
                value={metric.rank != null ? `#${metric.rank}` : null}
                percentile={percentile}
                valueColor={percentile != null ? percentileColor(percentile, colors) : undefined}
                onPress={metric.tappable ? onOpenTeams : undefined}
              />
            );
          })}
        </View>
      ) : null}
      {team.archetype_explanation ? (
        <AppText style={styles.explanation}>{team.archetype_explanation}</AppText>
      ) : null}
      {team.archetype_strengths.length > 0 ? (
        <DetailList
          label="Strengths"
          items={team.archetype_strengths}
          color={colors.success}
          icon="checkmark-circle-outline"
        />
      ) : null}
      {team.archetype_risks.length > 0 ? (
        <DetailList
          label="Risks"
          items={team.archetype_risks}
          color={colors.danger}
          icon="alert-circle-outline"
        />
      ) : null}
      {team.archetype_recommendations.length > 0 ? (
        <DetailList
          label="Recommendations"
          items={team.archetype_recommendations}
          color={colors.accent}
          icon="bulb-outline"
        />
      ) : null}
      {hasTradeContext ? (
        <AppText style={styles.tradeLine}>
          Trade behavior: {team.trade_tendency} ({team.trade_tendency_buy_count} acquired
          {'·'} {team.trade_tendency_sell_count} sent)
        </AppText>
      ) : null}
    </AnalyticsSection>
  );
}

/** Whether `team` carries any real analysis content beyond the plain rank
 * fields My Team's Overview snapshot already shows (Power/Starter/Draft
 * Capital/Age) — used to decide whether the Overview tab's "View Analysis"
 * affordance has anything real to point at. */
export function hasRosterAnalysis(team: TeamRanking): boolean {
  return Boolean(
    team.archetype_explanation ||
      team.archetype_strengths.length > 0 ||
      team.archetype_risks.length > 0 ||
      team.archetype_recommendations.length > 0 ||
      team.franchise_rank != null ||
      team.bench_rank != null,
  );
}

interface RankMetric {
  key: string;
  label: string;
  rank: number | null;
  tappable?: boolean;
}

function buildRankMetrics(team: TeamRanking): RankMetric[] {
  return [
    { key: 'power', label: 'Power', rank: team.power_rank, tappable: true },
    { key: 'franchise', label: 'Franchise', rank: team.franchise_rank, tappable: true },
    { key: 'draft', label: 'Draft Capital', rank: team.draft_capital_rank },
    { key: 'starters', label: 'Starters', rank: team.starter_rank },
    { key: 'bench', label: 'Bench', rank: team.bench_rank },
    { key: 'age', label: 'Age', rank: team.age_rank },
  ].filter((metric) => metric.rank != null);
}

/**
 * Strengths/Risks/Recommendations, previously a plain "• text" bullet list —
 * now a shared section label plus grouped `InsightRow`s (Magna Carta §28:
 * "short analytical conclusions should use one reusable component... do not
 * put every insight into a giant alert card"). One label per group instead
 * of per row (InsightRow's `label` is optional for exactly this case) since
 * every row in a group already shares the same category/icon/color.
 */
function DetailList({
  label,
  items,
  color,
  icon,
}: {
  label: string;
  items: string[];
  color: string;
  icon: React.ComponentProps<typeof InsightRow>['icon'];
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <View style={styles.detailGroup}>
      <AppText style={[styles.detailLabel, { color }]}>{label}</AppText>
      {items.map((item, index) => (
        <InsightRow
          key={`${label}-${index}`}
          icon={icon}
          color={color}
          headline={item}
          last={index === items.length - 1}
        />
      ))}
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    metricsRow: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
    explanation: {
      fontSize: 13,
      color: colors.textSecondary,
      lineHeight: 18,
      marginTop: spacing.md,
      paddingTop: spacing.md,
      borderTopWidth: StyleSheet.hairlineWidth,
      borderTopColor: colors.border,
    },
    detailGroup: { marginTop: spacing.sm },
    detailLabel: {
      fontSize: 11,
      fontWeight: '700',
      textTransform: 'uppercase',
      letterSpacing: 0.4,
      marginBottom: 2,
    },
    tradeLine: {
      fontSize: 12,
      color: colors.textTertiary,
      marginTop: spacing.sm,
    },
  });
}
