import React, { useEffect, useMemo, useState } from 'react';
import { FlatList, StyleSheet, TextInput, TouchableOpacity, View } from 'react-native';
import AppText from '../components/AppText';
import BrandHeaderBar from '../components/BrandHeaderBar';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useHeaderHeight } from '@react-navigation/elements';
import { Ionicons } from '@expo/vector-icons';

import EmptyState from '../components/EmptyState';
import BrandedSpinner from '../components/BrandedSpinner';
import GridBackground from '../components/GridBackground';
import EvaluationLensHeaderButton from '../components/EvaluationLensHeaderButton';
import GmStanceHeaderButton from '../components/GmStanceHeaderButton';
import LeagueSwitcherHeaderButton from '../components/LeagueSwitcherHeaderButton';
import OverallRatingBadge from '../components/OverallRatingBadge';
import PlayerIdentityRow from '../components/PlayerIdentityRow';
import ScreenInfoNote from '../components/ScreenInfoNote';
import { waiverInjuryDisplay } from '../components/WaiverRecommendationCard';
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

/**
 * One labeled row of filter chips — Position/Age/Status/Availability all
 * share this exact treatment (Magna Carta §18) instead of four subtly
 * different ad hoc rows. Chips wrap onto a second line on narrow screens
 * rather than requiring a horizontal swipe per row, matching Waivers'
 * canonical discovery-card filter treatment.
 */
function FilterGroup<T extends string>({
  label,
  options,
  value,
  onChange,
}: {
  label: string;
  options: readonly T[];
  value: T;
  onChange: (next: T) => void;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <View style={styles.filterGroup}>
      <AppText style={styles.filterLabel}>{label}</AppText>
      <View style={styles.pillRow}>
        {options.map((option) => (
          <TouchableOpacity
            key={option}
            style={[styles.pill, value === option && styles.pillActive]}
            onPress={() => onChange(option)}
          >
            <AppText style={[styles.pillText, value === option && styles.pillTextActive]}>{option}</AppText>
          </TouchableOpacity>
        ))}
      </View>
    </View>
  );
}

/**
 * Dense grouped-table row for the ranked player list — canonical
 * PlayerIdentityRow for identity (rank as the leading slot chip, tier +
 * opportunity classification, injury pill), plus a trailing value column
 * matching the value-first hierarchy every other ranked/board list on the
 * app now uses (see WaiversScreen's FreeAgentRow). Rows sit inside one
 * continuous bordered surface with hairline dividers rather than each being
 * its own card (Magna Carta §12) — with ~300 rows in play, an individually
 * bordered+animated card per row was also the main scroll-performance cost
 * this redesign removes.
 */
function PlayerRankRow({
  player,
  isFirst,
  isLast,
  onPress,
}: {
  player: RankedPlayer;
  isFirst: boolean;
  isLast: boolean;
  onPress: () => void;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const injury = waiverInjuryDisplay(player.injury_status);
  return (
    <View
      style={[
        styles.playerRow,
        isFirst && styles.playerRowFirst,
        isLast && styles.playerRowLast,
        !isLast && styles.playerRowDivider,
      ]}
    >
      <View style={styles.playerIdentity}>
        <PlayerIdentityRow
          playerId={player.player_id}
          name={player.name}
          position={player.position}
          team={player.team}
          tier={player.tier}
          slot={player.overall_rank != null ? String(player.overall_rank) : '—'}
          opportunityLabel={player.opportunity_label}
          injuryLabel={injury.label}
          injuryTone={injury.tone}
          ruledOut={injury.ruledOut}
          onPress={onPress}
          showDivider={false}
        />
      </View>
      <TouchableOpacity onPress={onPress} activeOpacity={0.7} style={styles.playerTrailing}>
        <AppText style={styles.playerScore}>{player.score != null ? Math.round(player.score) : '—'}</AppText>
        <View style={styles.playerTrailingChips}>
          {player.position && player.position_rank ? (
            <View style={styles.positionRankPill}>
              <AppText style={styles.positionRankText}>
                {player.position}
                {player.position_rank}
              </AppText>
            </View>
          ) : null}
          <OverallRatingBadge rating={player.overall_rating} />
          {player.usage_trend ? <UsageTrendPill trend={player.usage_trend} /> : null}
        </View>
      </TouchableOpacity>
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
          <LeagueSwitcherHeaderButton leagueId={leagueId} leagueName={leagueName} />
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
      <ScreenInfoNote text="Ranked by value for this league's scoring, roster, and format settings. OVR percentiles a player against others at their position — tap any player for the full breakdown." />

      {error ? <AppText style={styles.error}>{error}</AppText> : null}

      <View style={styles.discoveryCard}>
        <TextInput
          style={styles.searchInput}
          placeholder="Search players"
          value={search}
          onChangeText={setSearch}
          autoCapitalize="none"
          placeholderTextColor={colors.textTertiary}
        />
        <FilterGroup label="Position" options={POSITIONS} value={position} onChange={setPosition} />
        <FilterGroup label="Age" options={AGE_FILTERS} value={ageFilter} onChange={setAgeFilter} />
        <FilterGroup label="Status" options={STATUS_FILTERS} value={statusFilter} onChange={setStatusFilter} />
        <FilterGroup
          label="Availability"
          options={AVAILABILITY_FILTERS}
          value={availabilityFilter}
          onChange={setAvailabilityFilter}
        />
      </View>

      {loading ? (
        <BrandedSpinner style={styles.loading} />
      ) : (
        <FlatList
          data={filtered}
          keyExtractor={(item) => item.player_id}
          contentContainerStyle={[styles.listContent, { paddingBottom: orbClearance }]}
          initialNumToRender={16}
          maxToRenderPerBatch={16}
          windowSize={9}
          renderItem={({ item, index }) => (
            <PlayerRankRow
              player={item}
              isFirst={index === 0}
              isLast={index === filtered.length - 1}
              onPress={() => navigation.navigate('PlayerDetail', { player: item, leagueId, leagueName })}
            />
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
  discoveryCard: {
    marginHorizontal: spacing.lg,
    marginBottom: spacing.md,
    backgroundColor: colors.surface,
    borderRadius: radii.md,
    borderWidth: StyleSheet.hairlineWidth * 1.5,
    borderColor: colors.cardBorder,
    padding: spacing.md,
    gap: spacing.sm,
  },
  searchInput: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.sm,
    paddingHorizontal: spacing.md,
    paddingVertical: 10,
    fontSize: 15,
    backgroundColor: colors.background,
    color: colors.textPrimary,
  },
  filterGroup: { gap: 4 },
  filterLabel: {
    fontSize: 10.5,
    fontWeight: '700',
    color: colors.textTertiary,
    textTransform: 'uppercase',
    letterSpacing: 0.4,
  },
  pillRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.xs,
  },
  pill: {
    paddingHorizontal: spacing.sm,
    paddingVertical: 6,
    borderRadius: radii.pill,
    backgroundColor: colors.background,
    borderWidth: 1,
    borderColor: colors.cardBorder,
  },
  pillActive: { backgroundColor: colors.accent, borderColor: colors.accent, borderWidth: 1.5 },
  pillText: { fontSize: 12, fontWeight: '600', color: colors.textSecondary },
  pillTextActive: { color: '#fff', fontWeight: '700' },
  loading: { marginTop: spacing.xl },
  listContent: { paddingHorizontal: spacing.lg, paddingBottom: spacing.xl },
  playerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    paddingHorizontal: spacing.md,
    borderLeftWidth: StyleSheet.hairlineWidth * 1.5,
    borderRightWidth: StyleSheet.hairlineWidth * 1.5,
    borderColor: colors.cardBorder,
  },
  playerRowFirst: {
    borderTopWidth: StyleSheet.hairlineWidth * 1.5,
    borderTopLeftRadius: radii.md,
    borderTopRightRadius: radii.md,
  },
  playerRowLast: {
    borderBottomWidth: StyleSheet.hairlineWidth * 1.5,
    borderBottomLeftRadius: radii.md,
    borderBottomRightRadius: radii.md,
  },
  playerRowDivider: { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border },
  playerIdentity: { flex: 1 },
  playerTrailing: { alignItems: 'flex-end', gap: 3, paddingLeft: spacing.sm },
  playerScore: { fontSize: 16, fontWeight: '700', color: colors.accent },
  playerTrailingChips: { flexDirection: 'row', alignItems: 'center', gap: 4, flexWrap: 'wrap', justifyContent: 'flex-end' },
  positionRankPill: {
    backgroundColor: colors.backgroundElevated,
    borderRadius: radii.pill,
    paddingHorizontal: spacing.xs + 2,
    paddingVertical: 1,
  },
  positionRankText: { fontSize: 10, fontWeight: '700', color: colors.textSecondary },
  // Geometry copied from PositionBadge/PlayerIdentityRow's own chips so the
  // trend pill reads as one family of inline tags with them.
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
  error: { color: colors.danger, textAlign: 'center', marginHorizontal: spacing.lg, marginBottom: spacing.sm },
  });
}
