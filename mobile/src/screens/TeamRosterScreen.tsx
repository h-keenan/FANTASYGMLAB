import React, { useCallback, useMemo, useState } from 'react';
import { SectionList, StyleSheet, TouchableOpacity, View } from 'react-native';
import AppText from '../components/AppText';
import { useFocusEffect } from '@react-navigation/native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import AnimatedCard from '../components/AnimatedCard';
import BrandedSpinner from '../components/BrandedSpinner';
import GridBackground from '../components/GridBackground';
import PlayerAvatar from '../components/PlayerAvatar';
import { api, type PlayerSummary, type RankedPlayer, type TeamRanking } from '../lib/api';
import { useOrbClearance } from '../lib/orbLayout';
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

interface RankTile {
  label: string;
  value: string;
  /** Power/Franchise link out to the full league rankings (Teams screen) —
   * the other tiles here have no equivalent standalone screen to open. */
  tappable?: boolean;
}

function buildRankTiles(ranking: TeamRanking): RankTile[] {
  const tiles: RankTile[] = [];
  const push = (label: string, value: number | null, tappable = false) => {
    if (value != null) tiles.push({ label, value: `#${value}`, tappable });
  };
  push('Power', ranking.power_rank, true);
  push('Franchise', ranking.franchise_rank, true);
  push('Draft Capital', ranking.draft_capital_rank);
  push('Starters', ranking.starter_rank);
  push('Bench', ranking.bench_rank);
  push('Age', ranking.age_rank);
  return tiles;
}

type RosterSection = { title: string; data: RankedPlayer[] };

export default function TeamRosterScreen({ route, navigation }: Props) {
  const orbClearance = useOrbClearance();
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const { ownerName, playerIds, leagueId, leagueName, rosterId } = route.params;
  const [players, setPlayers] = useState<RankedPlayer[]>([]);
  const [ranking, setRanking] = useState<TeamRanking | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useScreenHeaderTitle(navigation, ownerName, leagueName);

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
    return <BrandedSpinner style={styles.center} />;
  }

  if (error) {
    return (
      <View style={styles.center}>
        <AppText style={styles.error}>{error}</AppText>
      </View>
    );
  }

  const rankTiles = ranking ? buildRankTiles(ranking) : [];

  return (
    <View style={styles.root}>
      <GridBackground />
      <SectionList
        style={styles.list}
        sections={sections}
        stickySectionHeadersEnabled={false}
        keyExtractor={(item) => item.player_id}
        contentContainerStyle={
          sections.length === 0 ? styles.emptyContainer : [styles.listContent, { paddingBottom: orbClearance }]
        }
        ListEmptyComponent={
          <AppText style={styles.empty}>
            No player data available for this roster (Sleeper doesn't have
            records for these player ids, or the roster is empty).
          </AppText>
        }
        ListHeaderComponent={
          ranking ? (
            <View style={styles.headerGroup}>
              {ranking.record_label ? <AppText style={styles.recordLabel}>{ranking.record_label}</AppText> : null}
              {rankTiles.length > 0 ? (
                <View style={styles.tileRow}>
                  {rankTiles.map((tile) =>
                    tile.tappable ? (
                      <TouchableOpacity
                        key={tile.label}
                        style={[styles.tile, styles.tileTappable]}
                        onPress={() => navigation.navigate('Teams', { leagueId, leagueName })}
                      >
                        <AppText style={styles.tileValue} numberOfLines={1}>
                          {tile.value}
                        </AppText>
                        <AppText style={styles.tileLabel}>{tile.label}</AppText>
                      </TouchableOpacity>
                    ) : (
                      <View key={tile.label} style={styles.tile}>
                        <AppText style={styles.tileValue} numberOfLines={1}>
                          {tile.value}
                        </AppText>
                        <AppText style={styles.tileLabel}>{tile.label}</AppText>
                      </View>
                    ),
                  )}
                </View>
              ) : null}
              {ranking.archetype_label ? (
                <AnimatedCard style={styles.archetypeCard}>
                  <View style={styles.archetypeHeaderRow}>
                    <AppText style={styles.archetypeLabel}>{ranking.archetype_label}</AppText>
                    {ranking.strategy_label ? (
                      <View style={styles.strategyPill}>
                        <AppText style={styles.strategyPillText}>{ranking.strategy_label}</AppText>
                      </View>
                    ) : null}
                  </View>
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
                    <ArchetypeDetailList
                      label="Recommendations"
                      items={ranking.archetype_recommendations}
                      color={colors.accent}
                    />
                  ) : null}
                </AnimatedCard>
              ) : null}
              {sections.length > 0 ? <AppText style={styles.sectionIntro}>Roster Core</AppText> : null}
            </View>
          ) : null
        }
        renderSectionHeader={({ section }) => (
          <View style={styles.sectionHeader}>
            <AppText style={styles.sectionHeaderText}>{section.title}</AppText>
          </View>
        )}
        renderItem={({ item }) => (
          <AnimatedCard
            style={styles.card}
            onPress={() => navigation.navigate('PlayerDetail', { player: item, leagueId, leagueName })}
          >
            <PlayerAvatar playerId={item.player_id} size={40} tier={item.tier} style={styles.avatar} />
            <View style={styles.nameColumn}>
              <AppText style={styles.name} numberOfLines={1}>
                {item.name ?? 'Unknown player'}
              </AppText>
              <AppText style={styles.meta}>
                {[item.team, item.opportunity_label ?? item.status].filter(Boolean).join(' · ') || '—'}
              </AppText>
            </View>
            {item.overall_rank != null ? (
              <View style={styles.rankPill}>
                <AppText style={styles.rankValue}>#{item.overall_rank}</AppText>
              </View>
            ) : null}
            {item.injury_status ? (
              <View style={styles.injuryPill}>
                <AppText style={styles.injuryText}>{item.injury_status}</AppText>
              </View>
            ) : null}
          </AnimatedCard>
        )}
      />
    </View>
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

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.background },
  list: { backgroundColor: 'transparent' },
  listContent: { padding: spacing.lg, paddingBottom: spacing.xl * 3, gap: spacing.sm },
  center: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: spacing.xl,
    backgroundColor: colors.background,
  },
  emptyContainer: { flex: 1, justifyContent: 'center' },
  empty: {
    textAlign: 'center',
    color: colors.textSecondary,
    paddingHorizontal: spacing.xl,
    lineHeight: 20,
  },
  headerGroup: { gap: spacing.md, marginBottom: spacing.sm },
  recordLabel: { fontSize: 13, fontWeight: '600', color: colors.textSecondary },
  tileRow: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
  tile: {
    flexBasis: '30%',
    flexGrow: 1,
    backgroundColor: colors.surface,
    borderRadius: radii.sm,
    borderWidth: 1,
    borderColor: colors.cardBorder,
    paddingVertical: spacing.sm,
    alignItems: 'center',
  },
  tileTappable: { borderColor: colors.accentMuted },
  tileValue: { fontSize: 16, fontWeight: '700', color: colors.accent },
  tileLabel: {
    fontSize: 10,
    fontWeight: '700',
    color: colors.textTertiary,
    textTransform: 'uppercase',
    letterSpacing: 0.4,
    marginTop: 2,
  },
  archetypeCard: { padding: spacing.lg, gap: spacing.sm },
  archetypeHeaderRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: spacing.sm },
  archetypeLabel: { fontSize: 16, fontWeight: '700', color: colors.textPrimary, flexShrink: 1 },
  strategyPill: {
    backgroundColor: colors.badgeBackground,
    borderRadius: radii.pill,
    paddingHorizontal: spacing.sm,
    paddingVertical: 3,
  },
  strategyPillText: { fontSize: 11, fontWeight: '700', color: colors.badgeText },
  archetypeExplanation: { fontSize: 13, color: colors.textSecondary, lineHeight: 18 },
  detailListGroup: { gap: 2 },
  detailListLabel: {
    fontSize: 11,
    fontWeight: '700',
    textTransform: 'uppercase',
    letterSpacing: 0.4,
    marginBottom: 2,
  },
  detailListItem: { fontSize: 13, color: colors.textSecondary, lineHeight: 18 },
  sectionIntro: {
    fontSize: 13,
    fontWeight: '700',
    color: colors.textTertiary,
    textTransform: 'uppercase',
    letterSpacing: 0.6,
    marginTop: spacing.sm,
  },
  sectionHeader: { paddingTop: spacing.sm, paddingBottom: spacing.xs },
  sectionHeaderText: {
    fontSize: 11,
    fontWeight: '700',
    color: colors.textTertiary,
    letterSpacing: 0.4,
  },
  card: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: spacing.md,
  },
  avatar: { marginRight: spacing.sm },
  nameColumn: { flex: 1, marginRight: spacing.sm },
  name: { fontSize: 15, fontWeight: '600', color: colors.textPrimary },
  meta: { fontSize: 12, color: colors.textSecondary, marginTop: 2 },
  rankPill: {
    backgroundColor: colors.background,
    borderRadius: radii.sm,
    paddingHorizontal: spacing.sm,
    paddingVertical: 4,
    marginRight: spacing.sm,
  },
  rankValue: { fontSize: 13, fontWeight: '700', color: colors.accent },
  injuryPill: {
    backgroundColor: colors.dangerMuted,
    borderRadius: radii.pill,
    paddingHorizontal: spacing.sm,
    paddingVertical: 3,
  },
  injuryText: { fontSize: 11, fontWeight: '700', color: colors.danger },
  error: { color: colors.danger, textAlign: 'center' },
  });
}
