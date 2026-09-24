import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { ScrollView, StyleSheet, TouchableOpacity, View } from 'react-native';
import AppText from '../components/AppText';
import { useFocusEffect } from '@react-navigation/native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useHeaderHeight } from '@react-navigation/elements';

import AnalyticsSection from '../components/AnalyticsSection';
import AnimatedCard from '../components/AnimatedCard';
import BrandHeaderBar from '../components/BrandHeaderBar';
import BrandedSpinner from '../components/BrandedSpinner';
import EmptyState from '../components/EmptyState';
import EvaluationLensHeaderButton from '../components/EvaluationLensHeaderButton';
import GmStanceHeaderButton from '../components/GmStanceHeaderButton';
import LeagueSwitcherHeaderButton from '../components/LeagueSwitcherHeaderButton';
import GridBackground from '../components/GridBackground';
import MetricCard from '../components/MetricCard';
import OverallRatingBadge from '../components/OverallRatingBadge';
import PlayerIdentityRow from '../components/PlayerIdentityRow';
import ScreenInfoNote from '../components/ScreenInfoNote';
import { waiverInjuryDisplay } from '../components/WaiverRecommendationCard';
import { api, type PlayerSummary, type RankedPlayer, type TeamRanking } from '../lib/api';
import { useOrbClearance } from '../lib/orbLayout';
import { percentileColor, percentileFromRank } from '../lib/percentile';
import { useScreenHeaderTitle } from '../lib/useScreenHeaderTitle';
import { useThemeMode } from '../context/ThemeModeContext';
import { radii, spacing, type ThemeColors } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

type Props = NativeStackScreenProps<RootStackParamList, 'TeamRoster'>;

const POSITION_ORDER = ['QB', 'RB', 'WR', 'TE', 'K', 'DEF'];

function toRankedPlayer(playerId: string, summary: PlayerSummary | undefined): RankedPlayer {
  return {
    player_id: playerId,
    name: summary?.full_name ?? null,
    position: summary?.position ?? null,
    team: summary?.team ?? null,
    age: summary?.age ?? null,
    status: summary?.status ?? null,
    injury_status: summary?.injury_status ?? null,
    tier: null,
    score: null,
    overall_rank: null,
    position_rank: null,
    rank_unavailable_reason: null,
    opportunity_label: null,
  };
}

function positionSortKey(position: string | null): number {
  const index = POSITION_ORDER.indexOf(position ?? '');
  return index === -1 ? POSITION_ORDER.length : index;
}

interface RankMetric {
  key: string;
  label: string;
  rank: number | null;
  /** Power/Franchise link out to the full league rankings (Teams screen) —
   * the other metrics here have no equivalent standalone screen to open. */
  tappable?: boolean;
}

function buildRankMetrics(ranking: TeamRanking): RankMetric[] {
  return [
    { key: 'power', label: 'Power', rank: ranking.power_rank, tappable: true },
    { key: 'franchise', label: 'Franchise', rank: ranking.franchise_rank, tappable: true },
    { key: 'draft', label: 'Draft Capital', rank: ranking.draft_capital_rank },
    { key: 'starters', label: 'Starters', rank: ranking.starter_rank },
    { key: 'bench', label: 'Bench', rank: ranking.bench_rank },
    { key: 'age', label: 'Age', rank: ranking.age_rank },
  ].filter((metric) => metric.rank != null);
}

type RosterSection = { title: string; data: RankedPlayer[] };

export default function TeamRosterScreen({ route, navigation }: Props) {
  const orbClearance = useOrbClearance();
  const headerHeight = useHeaderHeight();
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const { ownerName, playerIds, leagueId, leagueName, rosterId } = route.params;
  const [players, setPlayers] = useState<RankedPlayer[]>([]);
  const [ranking, setRanking] = useState<TeamRanking | null>(null);
  const [leagueSize, setLeagueSize] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useScreenHeaderTitle(navigation, ownerName, leagueName);

  useEffect(() => {
    navigation.setOptions({
      headerRight: () => (
        <View style={styles.headerButtonRow}>
          <LeagueSwitcherHeaderButton leagueId={leagueId} leagueName={leagueName} />
          <EvaluationLensHeaderButton leagueId={leagueId} />
          <GmStanceHeaderButton leagueId={leagueId} />
        </View>
      ),
    });
  }, [navigation, leagueId, styles]);

  useFocusEffect(
    useCallback(() => {
      let cancelled = false;

      async function load() {
        try {
          const [rankingsResult, summariesById, teamRankingsResult] = await Promise.all([
            api.getLeagueRankings(leagueId, { limit: 300 }),
            api.getPlayers(playerIds),
            api.getLeagueTeamRankings(leagueId).catch(() => ({ ok: true as const, teams: [], reason: 'unavailable' })),
          ]);
          if (cancelled) return;

          const rankedById = new Map(rankingsResult.players.map((p) => [p.player_id, p]));
          const rows = playerIds
            .map((playerId) => rankedById.get(playerId) ?? toRankedPlayer(playerId, summariesById[playerId]))
            .filter((row) => row.name !== null || rankedById.has(row.player_id))
            .sort((a, b) => positionSortKey(a.position) - positionSortKey(b.position));
          setPlayers(rows);

          setLeagueSize(teamRankingsResult.teams.length);
          const matchedRanking = teamRankingsResult.teams.find((team) => team.roster_id === rosterId) ?? null;
          setRanking(matchedRanking);
        } catch (err) {
          if (!cancelled) {
            setError(err instanceof Error ? err.message : 'Failed to load roster.');
          }
        } finally {
          if (!cancelled) setLoading(false);
        }
      }

      void load();
      return () => {
        cancelled = true;
      };
    }, [leagueId, playerIds, rosterId]),
  );

  const sections = useMemo<RosterSection[]>(() => {
    const byPosition = new Map<string, RankedPlayer[]>();
    for (const player of players) {
      const key = player.position ?? '—';
      const bucket = byPosition.get(key);
      if (bucket) bucket.push(player);
      else byPosition.set(key, [player]);
    }
    return Array.from(byPosition.entries())
      .sort((a, b) => positionSortKey(a[0]) - positionSortKey(b[0]))
      .map(([title, data]) => ({ title, data }));
  }, [players]);

  if (loading) {
    return <BrandedSpinner style={[styles.center, { paddingTop: headerHeight }]} />;
  }

  if (error) {
    return (
      <View style={[styles.center, { paddingTop: headerHeight }]}>
        <AppText style={styles.error}>{error}</AppText>
      </View>
    );
  }

  return (
    <View style={styles.root}>
      <GridBackground />
      <ScrollView
        style={styles.container}
        contentContainerStyle={[styles.content, { paddingBottom: orbClearance, paddingTop: headerHeight }]}
      >
        <BrandHeaderBar leagueId={leagueId} leagueName={leagueName} />
        <ScreenInfoNote text={`${ownerName}'s full roster in ${leagueName} — real value, rank, and role data for every player they own, grouped by position.`} />

        {ranking ? (
          <TeamSnapshotSection
            ranking={ranking}
            leagueSize={leagueSize}
            onOpenTeams={() => navigation.navigate('Teams', { leagueId, leagueName })}
          />
        ) : null}

        {sections.length === 0 ? (
          <EmptyState
            icon="people-outline"
            title="No roster data available"
            subtitle="Sleeper doesn't have records for these player ids, or this roster is empty."
          />
        ) : (
          <>
            <AppText style={styles.sectionLabel}>Roster</AppText>
            {sections.map((section) => (
              <View key={section.title} style={styles.positionGroup}>
                <AppText style={styles.positionLabel}>{section.title}</AppText>
                <AnimatedCard style={styles.groupCard}>
                  {section.data.map((player, index) => (
                    <RosterPlayerRow
                      key={player.player_id}
                      player={player}
                      showDivider={index < section.data.length - 1}
                      onPress={() => navigation.navigate('PlayerDetail', { player, leagueId, leagueName })}
                    />
                  ))}
                </AnimatedCard>
              </View>
            ))}
          </>
        )}
      </ScrollView>
    </View>
  );
}

/**
 * Team-level header for someone else's roster — same MetricCard/percentile
 * primitives MyTeamScreen's TeamAnalyticsSection and Player Detail's Stats
 * tab already use (Magna Carta §25-27), rather than this screen's old
 * bespoke bordered-tile grid with no percentile framing at all. Shows all
 * six TeamRanking rank fields (MyTeam's own snapshot only needs three, since
 * a viewer already knows their own team) plus the fuller archetype
 * breakdown this screen has always carried — strengths/risks/recommendations
 * text a quick "my team" glance doesn't need.
 */
function TeamSnapshotSection({
  ranking,
  leagueSize,
  onOpenTeams,
}: {
  ranking: TeamRanking;
  leagueSize: number;
  onOpenTeams: () => void;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const metrics = useMemo(() => buildRankMetrics(ranking), [ranking]);
  const outlook = ranking.archetype_label;

  return (
    <AnalyticsSection title="Team Snapshot" icon="podium-outline">
      {ranking.record_label || outlook ? (
        <View style={styles.snapshotHeaderRow}>
          {ranking.record_label ? <AppText style={styles.recordLabel}>{ranking.record_label}</AppText> : null}
          {outlook || ranking.strategy_label ? (
            <View style={styles.outlookRow}>
              {outlook ? (
                <View style={styles.outlookBadge}>
                  <AppText style={styles.outlookBadgeText}>{outlook.toUpperCase()}</AppText>
                </View>
              ) : null}
              {ranking.strategy_label ? (
                <View style={styles.strategyPill}>
                  <AppText style={styles.strategyPillText}>{ranking.strategy_label}</AppText>
                </View>
              ) : null}
            </View>
          ) : null}
        </View>
      ) : null}
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
      {ranking.archetype_explanation ? (
        <AppText style={styles.archetypeExplanation}>{ranking.archetype_explanation}</AppText>
      ) : null}
      {ranking.archetype_strengths.length > 0 ? (
        <ArchetypeDetailList label="Strengths" items={ranking.archetype_strengths} color={colors.success} />
      ) : null}
      {ranking.archetype_risks.length > 0 ? (
        <ArchetypeDetailList label="Risks" items={ranking.archetype_risks} color={colors.danger} />
      ) : null}
      {ranking.archetype_recommendations.length > 0 ? (
        <ArchetypeDetailList label="Recommendations" items={ranking.archetype_recommendations} color={colors.accent} />
      ) : null}
    </AnalyticsSection>
  );
}

function ArchetypeDetailList({ label, items, color }: { label: string; items: string[]; color: string }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <View style={styles.detailListGroup}>
      <AppText style={[styles.detailListLabel, { color }]}>{label}</AppText>
      {items.map((item, index) => (
        <AppText key={`${label}-${index}`} style={styles.detailListItem}>
          {'•'} {item}
        </AppText>
      ))}
    </View>
  );
}

/**
 * One roster row inside a position group's AnimatedCard — canonical
 * PlayerIdentityRow (league-wide rank as the leading slot chip, tier +
 * opportunity classification, injury pill) plus a trailing value column,
 * matching MyTeamScreen's LineupRow and PlayersScreen's PlayerRankRow
 * exactly rather than a third bespoke player-row layout (Magna Carta §19,
 * §47). `waiverInjuryDisplay` — already shared by Waivers and Players — is
 * reused here too since RankedPlayer only carries a raw `injury_status`
 * string, not the pre-resolved injury_label/ruled_out pair LineupPlayer has.
 */
function RosterPlayerRow({
  player,
  onPress,
  showDivider,
}: {
  player: RankedPlayer;
  onPress: () => void;
  showDivider: boolean;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const injury = waiverInjuryDisplay(player.injury_status);
  return (
    <TouchableOpacity
      style={[styles.compactRow, showDivider && styles.compactDivider]}
      onPress={onPress}
      activeOpacity={0.7}
    >
      <View style={styles.compactIdentity}>
        <PlayerIdentityRow
          playerId={player.player_id}
          name={player.name}
          position={player.position}
          team={player.team}
          tier={player.tier}
          slot={player.overall_rank != null ? String(player.overall_rank) : null}
          opportunityLabel={player.opportunity_label}
          injuryLabel={injury.label}
          injuryTone={injury.tone}
          ruledOut={injury.ruledOut}
          showDivider={false}
        />
      </View>
      <View style={styles.valueColumn}>
        <AppText style={styles.valueNumber}>{player.score != null ? Math.round(player.score) : '—'}</AppText>
        <AppText style={styles.valueLabel}>VALUE</AppText>
        <OverallRatingBadge rating={player.overall_rating} />
      </View>
    </TouchableOpacity>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
  headerButtonRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  root: { flex: 1, backgroundColor: colors.background },
  container: { flex: 1, backgroundColor: 'transparent' },
  content: { padding: spacing.lg, paddingBottom: spacing.xl * 4 },
  center: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: spacing.xl,
    backgroundColor: colors.background,
  },
  snapshotHeaderRow: { gap: spacing.xs, marginBottom: spacing.sm },
  recordLabel: { fontSize: 13, fontWeight: '600', color: colors.textSecondary },
  outlookRow: { flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', gap: spacing.xs },
  outlookBadge: {
    alignSelf: 'flex-start',
    backgroundColor: colors.accentMuted,
    borderRadius: radii.pill,
    paddingHorizontal: spacing.sm,
    paddingVertical: 4,
  },
  outlookBadgeText: { fontSize: 11, fontWeight: '700', color: colors.accent, letterSpacing: 0.4 },
  strategyPill: {
    backgroundColor: colors.badgeBackground,
    borderRadius: radii.pill,
    paddingHorizontal: spacing.sm,
    paddingVertical: 4,
  },
  strategyPillText: { fontSize: 11, fontWeight: '700', color: colors.badgeText },
  metricsRow: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm, marginTop: spacing.sm },
  archetypeExplanation: {
    fontSize: 13,
    color: colors.textSecondary,
    lineHeight: 18,
    marginTop: spacing.md,
    paddingTop: spacing.md,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.border,
  },
  detailListGroup: { gap: 2, marginTop: spacing.sm },
  detailListLabel: {
    fontSize: 11,
    fontWeight: '700',
    textTransform: 'uppercase',
    letterSpacing: 0.4,
    marginBottom: 2,
  },
  detailListItem: { fontSize: 13, color: colors.textSecondary, lineHeight: 18 },
  sectionLabel: {
    fontSize: 12,
    fontWeight: '700',
    color: colors.textTertiary,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginTop: spacing.md,
    marginBottom: spacing.sm,
  },
  positionGroup: { marginBottom: spacing.md },
  positionLabel: {
    fontSize: 11,
    fontWeight: '700',
    color: colors.textTertiary,
    letterSpacing: 0.4,
    marginBottom: spacing.xs,
  },
  // One grouped surface per position (QB, RB, WR, ...) with a
  // PlayerIdentityRow per player and hairline dividers between them,
  // instead of a separately bordered/backgrounded card per player — see
  // Magna Carta §12 (card philosophy) and MyTeamScreen's Starters/Bench
  // groupCard, which established this exact grouped-card pattern first.
  groupCard: { padding: spacing.md, paddingVertical: spacing.xs },
  compactRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: spacing.xs,
    gap: spacing.sm,
  },
  compactDivider: { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border },
  compactIdentity: { flex: 1 },
  valueColumn: { alignItems: 'flex-end', marginLeft: spacing.sm, gap: 2 },
  valueNumber: { fontSize: 16, fontWeight: '700', color: colors.accent },
  valueLabel: { fontSize: 9, fontWeight: '700', color: colors.textTertiary, letterSpacing: 0.4 },
  error: { color: colors.danger, textAlign: 'center' },
  });
}
