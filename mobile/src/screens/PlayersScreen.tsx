import React, { useEffect, useMemo, useState } from 'react';
import {
  FlatList,
  ScrollView,
  StyleSheet,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import AppText from '../components/AppText';
import ScreenHero from '../components/ScreenHero';
import BrandHeaderBar from '../components/BrandHeaderBar';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useHeaderHeight } from '@react-navigation/elements';
import { Ionicons } from '@expo/vector-icons';

import AnimatedCard from '../components/AnimatedCard';
import EmptyState from '../components/EmptyState';
import BrandedSpinner from '../components/BrandedSpinner';
import GridBackground from '../components/GridBackground';
import EvaluationLensHeaderButton from '../components/EvaluationLensHeaderButton';
import GmStanceHeaderButton from '../components/GmStanceHeaderButton';
import PlayerAvatar from '../components/PlayerAvatar';
import { resolvePlayerTier } from '../lib/playerTier';
import PositionBadge from '../components/PositionBadge';
import TierBadge from '../components/TierBadge';
import { api, type RankedPlayer, type UsageTrend, type ValuationLens } from '../lib/api';
import { useOrbClearance } from '../lib/orbLayout';
import { useScreenHeaderTitle } from '../lib/useScreenHeaderTitle';
import { useThemeMode } from '../context/ThemeModeContext';
import { useValuationLens } from '../context/ValuationLensContext';
import { radii, spacing, type ThemeColors } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

type Props = NativeStackScreenProps<RootStackParamList, 'Players'>;

const POSITIONS = ['ALL', 'QB', 'RB', 'WR', 'TE'];
const AGE_FILTERS = ['ALL', 'Under 25', '25-28', '29+'] as const;
const STATUS_FILTERS = ['ALL', 'Active', 'Inactive'] as const;
const AVAILABILITY_FILTERS = ['ALL', 'Healthy', 'Injured'] as const;

type AgeFilter = (typeof AGE_FILTERS)[number];
type StatusFilter = (typeof STATUS_FILTERS)[number];
type AvailabilityFilter = (typeof AVAILABILITY_FILTERS)[number];

function matchesAge(age: number | null, filter: AgeFilter): boolean {
  if (filter === 'ALL') return true;
  if (age == null) return false;
  if (filter === 'Under 25') return age < 25;
  if (filter === '25-28') return age >= 25 && age <= 28;
  return age >= 29;
}

function matchesStatus(status: string | null, filter: StatusFilter): boolean {
  if (filter === 'ALL') return true;
  const normalized = (status ?? '').trim().toLowerCase();
  return filter === 'Active' ? normalized === 'active' : normalized !== 'active' && normalized !== '';
}

function matchesAvailability(injuryStatus: string | null, filter: AvailabilityFilter): boolean {
  if (filter === 'ALL') return true;
  const hasInjury = Boolean((injuryStatus ?? '').trim());
  return filter === 'Injured' ? hasInjury : !hasInjury;
}

/**
 * Inline usage-trend pill for a ranked row — arrow plus the signed move, no
 * words, because the row is already dense; Player Detail carries the full
 * "trending up (high confidence)" sentence. The server only sends a
 * usage_trend at all once the read clears its confidence gate
 * (modules/rankings.py: recency_trend_display), so there is nothing to
 * threshold here.
 */
function UsageTrendPill({ trend }: { trend: UsageTrend }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const rising = trend.direction === 'up';
  const tint = rising ? colors.success : colors.danger;
  return (
    <View
      style={[
        styles.trendPill,
        { backgroundColor: rising ? colors.successMuted : colors.dangerMuted, borderColor: tint },
      ]}
    >
      <Ionicons name={rising ? 'arrow-up' : 'arrow-down'} size={9} color={tint} />
      <AppText style={[styles.trendPillText, { color: tint }]}>{trend.magnitude_pct}%</AppText>
    </View>
  );
}

export default function PlayersScreen({ route, navigation }: Props) {
  const orbClearance = useOrbClearance();
  const headerHeight = useHeaderHeight();
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const { leagueId, leagueName } = route.params;
  const { lens } = useValuationLens(leagueId);
  const [position, setPosition] = useState('ALL');
  const [ageFilter, setAgeFilter] = useState<AgeFilter>('ALL');
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('ALL');
  const [availabilityFilter, setAvailabilityFilter] = useState<AvailabilityFilter>('ALL');
  const [search, setSearch] = useState('');
  const [players, setPlayers] = useState<RankedPlayer[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useScreenHeaderTitle(navigation, 'Players', leagueName);

  useEffect(() => {
    navigation.setOptions({
      headerRight: () => (
        <View style={styles.headerButtonRow}>
          <EvaluationLensHeaderButton leagueId={leagueId} />
          <GmStanceHeaderButton leagueId={leagueId} />
        </View>
      ),
    });
  }, [navigation, leagueId, styles]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    (async () => {
      try {
        const result = await api.getLeagueRankings(leagueId, { lens, limit: 300 });
        if (!cancelled) setPlayers(result.players);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Failed to load players.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [leagueId, lens]);

  const filtered = useMemo(() => {
    if (!players) return [];
    const query = search.trim().toLowerCase();
    return players
      .filter((p) => position === 'ALL' || p.position === position)
      .filter((p) => matchesAge(p.age, ageFilter))
      .filter((p) => matchesStatus(p.status, statusFilter))
      .filter((p) => matchesAvailability(p.injury_status, availabilityFilter))
      .filter((p) => !query || (p.name ?? '').toLowerCase().includes(query));
  }, [players, position, ageFilter, statusFilter, availabilityFilter, search]);

  return (
    <View style={[styles.container, { paddingTop: headerHeight }]}>
      <GridBackground />
      <BrandHeaderBar leagueId={leagueId} leagueName={leagueName} />
      <ScreenHero title="PLAYERS" subtitle={leagueName} />
      <TextInput
        style={styles.searchInput}
        placeholder="Search players"
        value={search}
        onChangeText={setSearch}
        autoCapitalize="none"
        placeholderTextColor={colors.textTertiary}
      />

      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.filterRow}>
        {POSITIONS.map((option) => (
          <TouchableOpacity
            key={option}
            style={[styles.pill, position === option && styles.pillActive]}
            onPress={() => setPosition(option)}
          >
            <AppText style={[styles.pillText, position === option && styles.pillTextActive]}>{option}</AppText>
          </TouchableOpacity>
        ))}
      </ScrollView>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.filterRow}>
        {AGE_FILTERS.map((option) => (
          <TouchableOpacity
            key={option}
            style={[styles.pill, ageFilter === option && styles.pillActive]}
            onPress={() => setAgeFilter(option)}
          >
            <AppText style={[styles.pillText, ageFilter === option && styles.pillTextActive]}>{option}</AppText>
          </TouchableOpacity>
        ))}
      </ScrollView>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.filterRow}>
        {STATUS_FILTERS.map((option) => (
          <TouchableOpacity
            key={`status-${option}`}
            style={[styles.pill, statusFilter === option && styles.pillActive]}
            onPress={() => setStatusFilter(option)}
          >
            <AppText style={[styles.pillText, statusFilter === option && styles.pillTextActive]}>{option}</AppText>
          </TouchableOpacity>
        ))}
      </ScrollView>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.filterRow}>
        {AVAILABILITY_FILTERS.map((option) => (
          <TouchableOpacity
            key={`availability-${option}`}
            style={[styles.pill, availabilityFilter === option && styles.pillActive]}
            onPress={() => setAvailabilityFilter(option)}
          >
            <AppText style={[styles.pillText, availabilityFilter === option && styles.pillTextActive]}>{option}</AppText>
          </TouchableOpacity>
        ))}
      </ScrollView>

      {error ? <AppText style={styles.error}>{error}</AppText> : null}

      {loading ? (
        <BrandedSpinner style={styles.loading} />
      ) : (
        <FlatList
          data={filtered}
          keyExtractor={(item) => item.player_id}
          contentContainerStyle={[styles.listContent, { paddingBottom: orbClearance }]}
          renderItem={({ item }) => (
            <AnimatedCard
              style={styles.card}
              onPress={() => navigation.navigate('PlayerDetail', { player: item, leagueId, leagueName })}
            >
              <PlayerAvatar playerId={item.player_id} size={40} tier={item.tier} style={styles.avatar} />
              <View style={styles.rankBadge}>
                <AppText style={styles.rankText}>{item.overall_rank ?? '—'}</AppText>
              </View>
              <View style={styles.nameColumn}>
                <AppText style={styles.name} numberOfLines={1}>
                  {item.name ?? 'Unknown'}
                </AppText>
                <View style={styles.metaRow}>
                  <PositionBadge position={item.position} />
                  <AppText style={styles.meta} numberOfLines={1}>
                    {item.team}
                    {item.team && item.opportunity_label ? ' · ' : ''}
                    {item.opportunity_label ? (
                      <AppText style={[styles.meta, { color: resolvePlayerTier(item.tier).color }]}>
                        {item.opportunity_label}
                      </AppText>
                    ) : null}
                  </AppText>
                  {item.usage_trend ? <UsageTrendPill trend={item.usage_trend} /> : null}
                  <TierBadge storedTier={item.tier} />
                </View>
              </View>
              <AppText style={styles.score}>{item.score != null ? Math.round(item.score) : '—'}</AppText>
            </AnimatedCard>
          )}
          ListEmptyComponent={
            <EmptyState
              icon="search-outline"
              title="No players match"
              subtitle="Try a different search term or filter combination."
            />
          }
        />
      )}
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
  headerButtonRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  container: { flex: 1, backgroundColor: colors.background, paddingTop: spacing.md },
  searchInput: {
    marginHorizontal: spacing.lg,
    borderWidth: 1,
    borderColor: colors.cardBorder,
    borderRadius: radii.sm,
    paddingHorizontal: spacing.md,
    paddingVertical: 10,
    fontSize: 15,
    backgroundColor: colors.surface,
    color: colors.textPrimary,
    marginBottom: spacing.sm,
  },
  filterRow: {
    flexDirection: 'row',
    paddingHorizontal: spacing.lg,
    gap: spacing.xs,
    marginBottom: spacing.sm,
  },
  pill: {
    paddingHorizontal: spacing.sm,
    paddingVertical: 6,
    borderRadius: radii.pill,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.cardBorder,
  },
  pillActive: { backgroundColor: colors.accent, borderColor: colors.accent, borderWidth: 1.5 },
  pillText: { fontSize: 12, fontWeight: '600', color: colors.textSecondary },
  pillTextActive: { color: '#fff', fontWeight: '700' },
  loading: { marginTop: spacing.xl },
  listContent: { padding: spacing.lg, paddingTop: 0, paddingBottom: spacing.xl * 3, gap: spacing.sm },
  card: { flexDirection: 'row', alignItems: 'center', padding: spacing.md },
  avatar: { marginRight: spacing.sm },
  rankBadge: {
    width: 30,
    height: 26,
    borderRadius: radii.sm,
    backgroundColor: colors.badgeBackground,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: spacing.md,
  },
  rankText: { color: colors.badgeText, fontSize: 12, fontWeight: '700' },
  nameColumn: { flex: 1, marginRight: spacing.sm },
  name: { fontSize: 15, fontWeight: '600', color: colors.textPrimary },
  meta: { fontSize: 12, color: colors.textSecondary, flexShrink: 1 },
  metaRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs, marginTop: 3 },
  // Geometry copied from PositionBadge, its immediate neighbour in this row,
  // so the two read as one family of inline tags.
  trendPill: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    gap: 1,
    paddingHorizontal: spacing.xs + 2,
    paddingVertical: 1,
    borderRadius: radii.pill,
    borderWidth: 1,
  },
  trendPillText: { fontSize: 9, fontWeight: '800', letterSpacing: 0.3 },
  score: { fontSize: 15, fontWeight: '700', color: colors.textPrimary },
  empty: { textAlign: 'center', color: colors.textSecondary, marginTop: spacing.xl },
  error: { color: colors.danger, textAlign: 'center', marginHorizontal: spacing.lg, marginBottom: spacing.sm },
  });
}
