import React, { useEffect, useMemo, useState } from 'react';
import { FlatList, StyleSheet, TextInput, TouchableOpacity, View } from 'react-native';
import AppText from '../components/AppText';
import BrandHeaderBar from '../components/BrandHeaderBar';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useHeaderHeight } from '@react-navigation/elements';

import EmptyState from '../components/EmptyState';
import BrandedSpinner from '../components/BrandedSpinner';
import FilterDropdownButton from '../components/FilterDropdownButton';
import GridBackground from '../components/GridBackground';
import EvaluationLensHeaderButton from '../components/EvaluationLensHeaderButton';
import GmStanceHeaderButton from '../components/GmStanceHeaderButton';
import LeagueSwitcherHeaderButton from '../components/LeagueSwitcherHeaderButton';
import OverallRatingBadge from '../components/OverallRatingBadge';
import PlayerIdentityRow from '../components/PlayerIdentityRow';
import ScreenInfoNote from '../components/ScreenInfoNote';
import UsageTrendPill from '../components/UsageTrendPill';
import ViewModeToggle from '../components/ViewModeToggle';
import { waiverInjuryDisplay } from '../components/WaiverRecommendationCard';
import { api, type RankedPlayer, type ValuationLens } from '../lib/api';
import { toUserErrorMessage } from '../lib/errorMessages';
import { useOrbClearance } from '../lib/orbLayout';
import { useScreenHeaderTitle } from '../lib/useScreenHeaderTitle';
import { usePlayerListViewMode } from '../lib/viewModePreference';
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
 * Dense grouped-table row for the ranked player list — canonical
 * PlayerIdentityRow for identity (rank as the leading slot chip, tier +
 * opportunity classification, injury pill), plus a trailing value column
 * matching the value-first hierarchy every other ranked/board list on the
 * app now uses (see WaiversScreen's FreeAgentRow). Rows sit inside one
 * continuous bordered surface with hairline dividers rather than each being
 * its own card (Magna Carta §12) — with ~300 rows in play, an individually
 * bordered+animated card per row was also the main scroll-performance cost
 * this redesign removes.
 *
 * `grid`: coridian_'s 2-up compact card ask (Discord, 2026-10-09) for
 * screens that list a lot of players — same PlayerIdentityRow props (just
 * `layout="grid"`) and the exact same trailing chip set (score, position
 * rank, OVR, usage trend), only reflowed into a vertical card instead of a
 * grouped-table row. No information is dropped between the two modes.
 */
function PlayerRankRow({
  player,
  isFirst,
  isLast,
  grid = false,
  onPress,
}: {
  player: RankedPlayer;
  isFirst: boolean;
  isLast: boolean;
  grid?: boolean;
  onPress: () => void;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const injury = waiverInjuryDisplay(player.injury_status);
  const scoreText = player.score != null ? String(Math.round(player.score)) : '—';

  if (grid) {
    return (
      <View style={styles.gridCell}>
        <PlayerIdentityRow
          layout="grid"
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
        />
        {/* Score/position-rank/OVR/usage-trend chips render as a sibling
            footer strip rather than through PlayerIdentityRow's own
            trailingValue prop, matching how the list-mode row above composes
            its own trailing block beside (not inside) PlayerIdentityRow. */}
        <TouchableOpacity onPress={onPress} activeOpacity={0.7} style={styles.gridTrailingFooter}>
          <AppText style={styles.playerScore}>{scoreText}</AppText>
          <View style={styles.playerTrailingChips}>
            {player.position && player.position_rank ? (
              <View style={styles.positionRankPill}>
                <AppText style={styles.positionRankText}>
                  {player.position}
                  {player.position_rank}
                </AppText>
              </View>
            ) : null}
            <OverallRatingBadge rating={player.overall_rating} positionRank={player.position_rank} />
            {player.usage_trend ? <UsageTrendPill trend={player.usage_trend} /> : null}
          </View>
        </TouchableOpacity>
      </View>
    );
  }

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
        <AppText style={styles.playerScore}>{scoreText}</AppText>
        <View style={styles.playerTrailingChips}>
          {player.position && player.position_rank ? (
            <View style={styles.positionRankPill}>
              <AppText style={styles.positionRankText}>
                {player.position}
                {player.position_rank}
              </AppText>
            </View>
          ) : null}
          <OverallRatingBadge rating={player.overall_rating} positionRank={player.position_rank} />
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
  const { viewMode, setViewMode } = usePlayerListViewMode('players');

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
        if (!cancelled) setError(toUserErrorMessage(err, 'Failed to load players.'));
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
        <View style={styles.filterRow}>
          <FilterDropdownButton label="Position" options={POSITIONS} value={position} onChange={setPosition} />
          <FilterDropdownButton label="Age" options={AGE_FILTERS} value={ageFilter} onChange={setAgeFilter} />
          <FilterDropdownButton label="Status" options={STATUS_FILTERS} value={statusFilter} onChange={setStatusFilter} />
          <FilterDropdownButton
            label="Availability"
            options={AVAILABILITY_FILTERS}
            value={availabilityFilter}
            onChange={setAvailabilityFilter}
          />
          <ViewModeToggle value={viewMode} onChange={setViewMode} />
        </View>
      </View>

      {loading ? (
        <BrandedSpinner style={styles.loading} />
      ) : (
        <FlatList
          // Forces a clean remount on toggle — RN's FlatList explicitly does
          // not support changing `numColumns` on the fly (its own invariant
          // warning says to change `key` instead), since the internal row
          // layout math is set up once per mount.
          key={viewMode}
          data={filtered}
          keyExtractor={(item) => item.player_id}
          numColumns={viewMode === 'grid' ? 2 : 1}
          columnWrapperStyle={viewMode === 'grid' ? styles.gridRow : undefined}
          contentContainerStyle={[styles.listContent, { paddingBottom: orbClearance }]}
          initialNumToRender={16}
          maxToRenderPerBatch={16}
          windowSize={9}
          renderItem={({ item, index }) => (
            <PlayerRankRow
              player={item}
              isFirst={index === 0}
              isLast={index === filtered.length - 1}
              grid={viewMode === 'grid'}
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
  // Position/Age/Status/Availability now render as one wrapping row of
  // compact dropdown buttons (FilterDropdownButton) instead of four full
  // rows of always-expanded pills — coridian_, Discord: "these filter pills
  // need to be grouped and turn into drop down menus because this is
  // ridiculous."
  filterRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.xs,
  },
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
  // Grid (2-up compact card) mode — see PlayerRankRow's `grid` branch.
  // `width: '48%'` + `columnWrapperStyle`'s `justifyContent: 'space-between'`
  // (rather than `flex: 1` + a `gap`) is the deliberate choice: it keeps an
  // unpaired last card (odd total count) from stretching to double width
  // instead of sitting flush left like every other card.
  gridRow: { justifyContent: 'space-between', marginBottom: spacing.sm },
  gridCell: {
    width: '48%',
    backgroundColor: colors.surface,
    borderRadius: radii.md,
    borderWidth: StyleSheet.hairlineWidth * 1.5,
    borderColor: colors.cardBorder,
    padding: spacing.sm,
  },
  gridTrailingFooter: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginTop: spacing.xs,
    paddingTop: spacing.xs,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.border,
  },
  error: { color: colors.danger, textAlign: 'center', marginHorizontal: spacing.lg, marginBottom: spacing.sm },
  });
}
