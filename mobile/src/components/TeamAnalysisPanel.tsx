import React, { useMemo } from 'react';
import { StyleSheet, View } from 'react-native';

import AnalyticsSection from './AnalyticsSection';
import AppText from './AppText';
import InsightRow from './InsightRow';
import MetricCard from './MetricCard';
import { useThemeMode } from '../context/ThemeModeContext';
import type { TeamRanking } from '../lib/api';
import { formatRank, percentileColor, percentileFromRank } from '../lib/percentile';
import { spacing, type ThemeColors } from '../theme';

/**
 * Shared "roster analysis" content: the full TeamRanking rank matrix
 * (Roster Power/Franchise/Draft Capital/Starters/Bench/Age) plus the archetype
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
  showExplanations,
  onOpenTeams,
  onOpenDraftCenter,
  onOpenStarters,
  onOpenBench,
  onOpenAge,
}: {
  team: TeamRanking;
  leagueSize: number;
  /** Density setting (DensityContext's `showExplanations`) — hides the
   * archetype "why" narrative + strengths/risks/recommendations elaboration
   * in Compact mode, while the rank matrix above (the actual Roster Power/
   * Starter/Draft Capital/etc. calls) always stays visible. */
  showExplanations: boolean;
  onOpenTeams?: () => void;
  /** Draft Capital tile destination — Draft Center's own posture header
   * surfaces this exact `draft_capital_rank` for the signed-in user's team,
   * so it's a real drill-down, not a re-navigation to the same data. */
  onOpenDraftCenter?: () => void;
  /** Starters/Bench tiles switch this same screen's own local tab instead
   * of navigating cross-screen — My Team's Overview tab already renders the
   * complete starting lineup (merged in from the old separate Starters tab)
   * and Bench renders the full bench, so drilling in means switching tabs,
   * not opening a new route. Left undefined for TeamRosterScreen's
   * page-local reuse of this same rank matrix (viewing a league-mate's
   * roster, which has no Overview/Bench tabs of its own to switch to) —
   * those two tiles simply stay non-tappable there. */
  onOpenStarters?: () => void;
  onOpenBench?: () => void;
  /** Age tile destination — same shared Teams leaderboard Roster Power/
   * Franchise already open, pointed at the Age metric (see TeamsScreen's
   * `METRIC_CONFIG`) instead of a screen that doesn't exist. */
  onOpenAge?: () => void;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const metrics = useMemo(
    () => buildRankMetrics(team, { onOpenTeams, onOpenDraftCenter, onOpenStarters, onOpenBench, onOpenAge }),
    [team, onOpenTeams, onOpenDraftCenter, onOpenStarters, onOpenBench, onOpenAge],
  );
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
                icon={metric.icon}
                value={metric.rank != null ? formatRank(metric.rank, metric.tied) : null}
                percentile={percentile}
                valueColor={percentile != null ? percentileColor(percentile, colors) : undefined}
                onPress={metric.onPress}
              />
            );
          })}
        </View>
      ) : null}
      {showExplanations && team.archetype_explanation ? (
        <AppText style={styles.explanation}>{team.archetype_explanation}</AppText>
      ) : null}
      {showExplanations && team.archetype_strengths.length > 0 ? (
        <DetailList
          label="Strengths"
          items={team.archetype_strengths}
          color={colors.success}
          icon="checkmark-circle-outline"
        />
      ) : null}
      {showExplanations && team.archetype_risks.length > 0 ? (
        <DetailList
          label="Risks"
          items={team.archetype_risks}
          color={colors.danger}
          icon="alert-circle-outline"
        />
      ) : null}
      {showExplanations && team.archetype_recommendations.length > 0 ? (
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
 * fields My Team's Overview snapshot already shows (Roster Power/Starter/
 * Draft Capital/Age) — used to decide whether the Overview tab's "View
 * Analysis" affordance has anything real to point at. */
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

type IoniconName = React.ComponentProps<typeof InsightRow>['icon'];

interface RankMetric {
  key: string;
  label: string;
  /** Leading glyph on the tile label (coridian_: these tags "need some sort
   * of glyph icon, something to pop") — chosen per metric below, same
   * Ionicons set already used throughout the app. */
  icon: IoniconName;
  rank: number | null;
  /** 2+ teams share this exact dense rank — renders "T4" instead of "#4"
   * (see modules.league_rankings.add_rank_tie_metadata on the backend). */
  tied: boolean;
  /** Presence, not a separate boolean, is what makes a tile tappable — same
   * `onPress`-driven pattern MetricCard/InsightRow already use elsewhere. */
  onPress?: () => void;
}

/**
 * Age used to have no destination anywhere in the app — there was no
 * standalone screen that answered "why is my roster's age rank what it
 * is." TeamsScreen (the shared league leaderboard Roster Power/Franchise
 * already open) now takes a `metric` param and already has every team's
 * `age_rank`/`average_age` from the same `getLeagueTeamRankings` call it
 * uses for Roster Power, so Age opens that same leaderboard sorted/labeled by Age
 * instead of needing a new screen or per-player breakdown.
 */
function buildRankMetrics(
  team: TeamRanking,
  callbacks: {
    onOpenTeams?: () => void;
    onOpenDraftCenter?: () => void;
    onOpenStarters?: () => void;
    onOpenBench?: () => void;
    onOpenAge?: () => void;
  },
): RankMetric[] {
  const metrics: RankMetric[] = [
    // flash: Roster Power = overall roster strength/firepower.
    { key: 'power', label: 'Roster Power', icon: 'flash', rank: team.power_rank, tied: team.power_rank_tied, onPress: callbacks.onOpenTeams },
    // star: Franchise = long-term franchise value, not a single-season read.
    { key: 'franchise', label: 'Franchise', icon: 'star', rank: team.franchise_rank, tied: team.franchise_rank_tied, onPress: callbacks.onOpenTeams },
    // file-tray-stacked: Draft Capital = the stack of picks a team holds.
    { key: 'draft', label: 'Draft Capital', icon: 'file-tray-stacked-outline', rank: team.draft_capital_rank, tied: team.draft_capital_rank_tied, onPress: callbacks.onOpenDraftCenter },
    // american-football: Starters = the active lineup on the field.
    { key: 'starters', label: 'Starters', icon: 'american-football-outline', rank: team.starter_rank, tied: team.starter_rank_tied, onPress: callbacks.onOpenStarters },
    // people: Bench = the depth of reserve players behind the starters.
    { key: 'bench', label: 'Bench', icon: 'people-outline', rank: team.bench_rank, tied: team.bench_rank_tied, onPress: callbacks.onOpenBench },
    // hourglass: Age = where a roster sits on its aging timeline.
    { key: 'age', label: 'Age', icon: 'hourglass-outline', rank: team.age_rank, tied: team.age_rank_tied, onPress: callbacks.onOpenAge },
  ];
  return metrics.filter((metric) => metric.rank != null);
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
