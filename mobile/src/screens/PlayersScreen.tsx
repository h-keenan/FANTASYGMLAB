import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { FlatList, ScrollView, StyleSheet, View } from 'react-native';
import { ReSettle } from '../components/Motion';
import PressableScale from '../components/PressableScale';
import CompactModule from '../components/CompactModule';
import PickGroupList from '../components/PickGroupList';
import DraftPickAssetRow from '../components/DraftPickAssetRow';
import { pickProvenance } from '../lib/pickGroups';
import AppText from '../components/AppText';
import GlassCard from '../components/GlassCard';
import PageFamilyTabs from '../components/PageFamilyTabs';
import ExpandingSearch from '../components/ExpandingSearch';
import PageControlRow, { ViewTabs } from '../components/PageControlRow';
import CollegeScoutingPanel from '../components/CollegeScoutingPanel';
import { needPositionsFrom, type ScoutingLens } from '../lib/scoutingLens';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { Ionicons } from '@expo/vector-icons';
import { useHeaderHeight } from '@react-navigation/elements';

import EmptyState from '../components/EmptyState';
import { SkeletonList } from '../components/Skeleton';
import FilterSheet from '../components/FilterSheet';
import { singleValue, valuesFromSingles, type FilterGroup, type FilterValues } from '../lib/filterSheet';
import GridBackground from '../components/GridBackground';
import EvaluationLensHeaderButton from '../components/EvaluationLensHeaderButton';
import GmStanceHeaderButton from '../components/GmStanceHeaderButton';
import LeagueSwitcherHeaderButton from '../components/LeagueSwitcherHeaderButton';
import OverallRatingBadge from '../components/OverallRatingBadge';
import PlayerIdentityRow from '../components/PlayerIdentityRow';
import PlayerAccordionRow, { usePlayerAccordion } from '../components/PlayerAccordionRow';
import type { PlayerFact } from '../lib/playerAnatomy';
import { badgeFromInjury } from '../lib/playerBadges';
import UsageTrendPill from '../components/UsageTrendPill';
import ValuesCredit from '../components/ValuesCredit';
import { waiverInjuryDisplay } from '../components/WaiverRecommendationCard';
import { mergeSearchMatches, useLeaguePlayerSearch } from '../lib/leaguePlayerSearch';
import {
  OVERALL_RATING_SORT_KEY,
  PLAYERS_AGE_FILTERS,
  PLAYERS_AVAILABILITY_FILTERS,
  PLAYERS_POSITION_FILTERS,
  PLAYERS_ROSTER_FILTERS,
  PLAYERS_STATUS_FILTERS,
  VALUE_SORT_KEY,
  buildPlayersSortOptions,
  filterPlayers,
  findPlayersStat,
  formatPlayersPercentile,
  formatPlayersStatValue,
  sortPlayers,
  type PlayersAgeFilter,
  type PlayersAvailabilityFilter,
  type PlayersRosterFilter,
  type PlayersSortMode,
  type PlayersSortOption,
  type PlayersStatusFilter,
} from '../lib/playersPresentation';
import { picksSummaryParts } from '../lib/playersModules';
import { api, type DraftPickAsset, type LeagueIdpValuesResponse, type RankedPlayer, type ValuationLens } from '../lib/api';
import {
  IDP_CONFIDENCE_LABEL,
  idpMethodNote,
  idpRowsAsRankedPlayers,
  isIdpPositionFilter,
  playersPositionOptions,
} from '../lib/idpPresentation';
import { toUserErrorMessage } from '../lib/errorMessages';
import { useOrbClearance } from '../lib/orbLayout';
import { useScreenHeaderTitle } from '../lib/useScreenHeaderTitle';
import { usePlayerListViewMode } from '../lib/viewModePreference';
import { tradeShortcutsFor } from '../lib/tradeShortcuts';
import { useRosterOwnership } from '../lib/useRosterOwnership';
import { useThemeMode } from '../context/ThemeModeContext';
import { useValuationLens } from '../context/ValuationLensContext';
import { radii, spacing, type ThemeColors } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';
import { usePlayerQuickView } from '../context/PlayerQuickViewContext';
import ErrorState from '../components/ErrorState';

type Props = NativeStackScreenProps<RootStackParamList, 'Players'>;
type PlayersTab = 'players' | 'prospects';
const PLAYERS_VIEWS = ['Players', 'Prospects'] as const;

const POSITIONS = PLAYERS_POSITION_FILTERS;

/**
 * Compact icon actions for a Players row (tap-depth audit #1/#2) — web's
 * Players rows carry "Add to Trade" too. Rendered only when the caller
 * passes a handler, i.e. once ownership is known: Add to Trade for any
 * rostered player, Find trades only for the user's own.
 */
function RowTradeActions({
  playerName,
  onAddToTrade,
  onFindTrades,
}: {
  playerName: string;
  onAddToTrade?: () => void;
  onFindTrades?: () => void;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  if (!onAddToTrade && !onFindTrades) return null;
  return (
    <View style={styles.rowActions}>
      {onAddToTrade ? (
        <PressableScale
          onPress={onAddToTrade}
          hitSlop={6}
          style={[styles.rowActionButton, styles.rowActionAccent]}
          accessibilityRole="button"
          accessibilityLabel={`Add ${playerName} to a trade`}
        >
          <Ionicons name="swap-horizontal-outline" size={18} color={colors.accent} />
        </PressableScale>
      ) : null}
      {onFindTrades ? (
        <PressableScale
          onPress={onFindTrades}
          hitSlop={6}
          style={styles.rowActionButton}
          accessibilityRole="button"
          accessibilityLabel={`Find trades for ${playerName}`}
        >
          <Ionicons name="search-outline" size={18} color={colors.accent} />
        </PressableScale>
      ) : null}
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
  onAddToTrade,
  onFindTrades,
  idpConfidence,
  sortFact,
  open = false,
  onToggle = () => {},
}: {
  open?: boolean;
  onToggle?: () => void;
  /** Set only for IDP rows: shows the projection basis instead of OVR. */
  idpConfidence?: string;
  /** The selected stat sort column's value for this row (hidden for Value/OVR), as an expanded-tile fact. */
  sortFact?: PlayerFact | null;
  player: RankedPlayer;
  isFirst: boolean;
  isLast: boolean;
  grid?: boolean;
  onPress: () => void;
  onAddToTrade?: () => void;
  onFindTrades?: () => void;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const injury = waiverInjuryDisplay(player.injury_status);
  const scoreText = player.score != null ? String(Math.round(player.score)) : '—';
  const tradeActions = (
    <RowTradeActions playerName={player.name ?? 'this player'} onAddToTrade={onAddToTrade} onFindTrades={onFindTrades} />
  );

  if (grid) {
    return (
      <GlassCard compact style={styles.gridCell}>
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
        <View style={styles.gridFooterRow}>
        <PressableScale onPress={onPress} style={styles.gridTrailingFooter}>
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
            {idpConfidence ? (
              <View style={styles.positionRankPill}>
                <AppText style={styles.positionRankText}>{IDP_CONFIDENCE_LABEL[idpConfidence] ?? idpConfidence}</AppText>
              </View>
            ) : (
              <OverallRatingBadge rating={player.overall_rating} positionRank={player.position_rank} />
            )}
            {player.usage_trend ? <UsageTrendPill trend={player.usage_trend} /> : null}
          </View>
        </PressableScale>
        {tradeActions}
        </View>
      </GlassCard>
    );
  }

  // List layout: the shared inline-accordion player row (compact two-line row, one open at a time, swells into a tile).
  const extraFacts: PlayerFact[] = [];
  if (player.position && player.position_rank) extraFacts.push({ key: 'posrank', label: 'POS RANK', value: `${player.position}${player.position_rank}` });
  if (idpConfidence) extraFacts.push({ key: 'basis', label: 'BASIS', value: IDP_CONFIDENCE_LABEL[idpConfidence] ?? idpConfidence });
  if (player.usage_trend) extraFacts.push({ key: 'usage', label: 'USAGE', value: player.usage_trend.label ?? 'Trending' });
  if (sortFact) extraFacts.push(sortFact);
  const injuryKind = badgeFromInjury(injury.label);
  return (
    <View style={[isFirst && styles.playerRowFirst, isLast && styles.playerRowLast]}>
      <PlayerAccordionRow
        player={{ id: player.player_id, name: player.name ?? 'Player', position: player.position, team: player.team, age: player.age, tier: player.tier }}
        mode="desk"
        value={player.score ?? null}
        ovr={idpConfidence ? null : player.overall_rating ?? null}
        extraFacts={extraFacts}
        badges={injuryKind ? [{ kind: injuryKind, detail: injury.label }] : []}
        open={open}
        onToggle={onToggle}
        onOpenProfile={onPress}
      >
        {tradeActions}
      </PlayerAccordionRow>
    </View>
  );
}

export default function PlayersScreen({ route, navigation }: Props) {
  const { openPlayer: openQuickView } = usePlayerQuickView();
  const orbClearance = useOrbClearance();
  const headerHeight = useHeaderHeight();
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const { leagueId, leagueName } = route.params;
  // Players and Prospects tabs (College Scouting is now the Prospects tab): `tab: 'prospects'` from the orb, the Today prompt, More.
  const requestedTab = route.params.tab;
  const [tab, setTab] = useState<PlayersTab>(requestedTab ?? 'players');
  useEffect(() => {
    if (requestedTab) setTab(requestedTab);
  }, [requestedTab]);
  const { lens } = useValuationLens(leagueId);
  // Prospects' "For my league" overlay (needs + your pick slots), loaded the first time the tab opens; best-effort.
  const [scoutingLens, setScoutingLens] = useState<ScoutingLens | null>(null);
  useEffect(() => {
    if (tab !== 'prospects' || scoutingLens) return;
    let cancelled = false;
    Promise.all([
      api.getLeagueDraftPicks(leagueId).then((r) => r.picks, () => [] as DraftPickAsset[]),
      api.getMyRoster(leagueId).then((r) => String(r?.roster?.roster_id ?? ''), () => ''),
      api.getLeagueMyTeamNeeds(leagueId).then((r) => r?.position_groups ?? null, () => null),
    ]).then(([picks, rosterId, needs]) => {
      if (cancelled) return;
      const myPicks = rosterId ? picks.filter((pick) => pick.owner_roster_id === rosterId) : [];
      if (needs || myPicks.length) setScoutingLens({ needPositions: needPositionsFrom(needs), myPicks });
    });
    return () => {
      cancelled = true;
    };
  }, [tab, leagueId, scoutingLens]);
  const [position, setPosition] = useState('ALL');
  const [ageFilter, setAgeFilter] = useState<PlayersAgeFilter>('ALL');
  const [statusFilter, setStatusFilter] = useState<PlayersStatusFilter>('ALL');
  const [availabilityFilter, setAvailabilityFilter] = useState<PlayersAvailabilityFilter>('ALL');
  const [rosterFilter, setRosterFilter] = useState<PlayersRosterFilter>('ALL');
  const [sortKey, setSortKey] = useState<string>(VALUE_SORT_KEY);
  const [sortMode, setSortMode] = useState<PlayersSortMode>('raw');
  const [picks, setPicks] = useState<DraftPickAsset[]>([]);
  const [search, setSearch] = useState('');
  const [searchOpen, setSearchOpen] = useState(false);
  const [players, setPlayers] = useState<RankedPlayer[] | null>(null);
  const [idp, setIdp] = useState<LeagueIdpValuesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);
  const { viewMode, setViewMode } = usePlayerListViewMode('players');
  const ownership = useRosterOwnership(leagueId);
  const rosteredPlayerIds = ownership?.rosteredPlayerIds;
  const rosterOwnershipKnown = Boolean(rosteredPlayerIds && rosteredPlayerIds.size > 0);
  useEffect(() => {
    let cancelled = false;
    api.getLeagueDraftPicks(leagueId).then(
      (r) => { if (!cancelled) setPicks(r.picks); },
      () => { if (!cancelled) setPicks([]); },
    );
    return () => { cancelled = true; };
  }, [leagueId]);
  const accordion = usePlayerAccordion();
  const { openId: accordionOpenId, toggle: toggleAccordionRow } = accordion;
  const onNavigateTrades = useCallback(
    (player: RankedPlayer, initialTab: 'make' | 'search') =>
      navigation.navigate('Trades', { leagueId, leagueName, initialTab, tradePlayer: player }),
    [navigation, leagueId, leagueName],
  );

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
    setError(null);
    (async () => {
      try {
        const result = await api.getLeagueRankings(leagueId, { lens, limit: 300 });
        if (!cancelled) setPlayers(result.players);
        // Optional: non-IDP leagues get `idp: false`; a failure leaves offense untouched.
        const idpResult = await api.getLeagueIdpValues(leagueId).catch(() => null);
        if (!cancelled) setIdp(idpResult);
      } catch (err) {
        if (!cancelled) setError(toUserErrorMessage(err, 'Failed to load players.'));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [leagueId, lens, reloadToken]);

  // Defenders only form the pool under a DL/LB/DB chip, so offensive ranks
  // never mix with the model-value scale.
  const idpPlayers = useMemo(() => idpRowsAsRankedPlayers(idp), [idp]);
  const idpConfidenceById = useMemo(() => {
    const map = new Map<string, string>();
    for (const row of idp?.players ?? []) map.set(row.player_id, row.confidence);
    return map;
  }, [idp]);
  const positionOptions = useMemo(() => playersPositionOptions(POSITIONS, idp), [idp]);
  const idpSelected = idpPlayers.length > 0 && isIdpPositionFilter(position);

  // The rankings window is the top 300; search also asks the server so a lower-ranked
  // player (e.g. a rookie backup) is found instead of silently absent.
  const searchMatches = useLeaguePlayerSearch(leagueId, lens, search);

  const offensePool = useMemo(
    () => (players ? mergeSearchMatches(players, searchMatches) : null),
    [players, searchMatches],
  );
  const pool = idpSelected ? idpPlayers : offensePool;
  const filtered = useMemo(
    () =>
      pool
        ? filterPlayers(pool, { search, position, ageFilter, statusFilter, availabilityFilter, rosterFilter, rosteredPlayerIds })
        : [],
    [pool, search, position, ageFilter, statusFilter, availabilityFilter, rosterFilter, rosteredPlayerIds],
  );
  // Sort options reflect the stats the filtered pool carries; a stale key falls back to Value.
  const sortOptions = useMemo(() => buildPlayersSortOptions(filtered), [filtered]);
  const activeSortOption: PlayersSortOption = sortOptions.find((option) => option.key === sortKey) ?? sortOptions[0];
  const sortedPlayers = useMemo(
    () => (activeSortOption.key === VALUE_SORT_KEY ? filtered : sortPlayers(filtered, activeSortOption.key, sortMode)),
    [filtered, activeSortOption.key, sortMode],
  );
  const lastIndex = sortedPlayers.length - 1;
  const renderPlayerItem = useCallback(
    ({ item, index }: { item: RankedPlayer; index: number }) => {
      // Trade shortcuts are offense-only until the trade engines value defenders.
      const shortcuts = idpSelected
        ? { canAddToTrade: false, canFindTrades: false }
        : tradeShortcutsFor(item.player_id, ownership);
      let sortFactLabel: string | undefined;
      let sortFactValue: string | undefined;
      if (activeSortOption.key !== VALUE_SORT_KEY && activeSortOption.key !== OVERALL_RATING_SORT_KEY) {
        const stat = findPlayersStat(item, activeSortOption.key);
        if (stat) {
          const pct = sortMode === 'percentile';
          sortFactLabel = `${stat.label}${pct ? ' pct' : ''}`.toUpperCase();
          sortFactValue = pct ? (stat.percentile != null ? formatPlayersPercentile(stat.percentile) : '—') : formatPlayersStatValue(stat);
        }
      }
      return (
        <PlayerListItem
          item={item}
          sortFactLabel={sortFactLabel}
          sortFactValue={sortFactValue}
          index={index}
          isLast={index === lastIndex}
          grid={viewMode === 'grid'}
          open={accordionOpenId === item.player_id}
          idpConfidence={idpSelected ? idpConfidenceById.get(item.player_id) ?? 'low' : undefined}
          canAddToTrade={shortcuts.canAddToTrade}
          canFindTrades={shortcuts.canFindTrades}
          leagueId={leagueId}
          leagueName={leagueName}
          onToggleRow={toggleAccordionRow}
          onOpenPlayer={openQuickView}
          onNavigateTrades={onNavigateTrades}
        />
      );
    },
    [idpSelected, ownership, activeSortOption.key, sortMode, lastIndex, viewMode, accordionOpenId, idpConfidenceById, leagueId, leagueName, toggleAccordionRow, openQuickView, onNavigateTrades],
  );

  // One Filters button instead of four dropdown pills (FilterSheet, same groups as web).
  const filterGroups = useMemo<FilterGroup[]>(
    () => [
      { id: 'position', label: 'Position', anyValue: 'ALL', options: positionOptions.map((pos) => ({ value: pos, label: pos === 'ALL' ? 'Any' : pos })) },
      { id: 'age', label: 'Age', anyValue: 'ALL', options: PLAYERS_AGE_FILTERS.map((option) => ({ value: option, label: option === 'ALL' ? 'Any age' : option })) },
      { id: 'status', label: 'Status', anyValue: 'ALL', options: PLAYERS_STATUS_FILTERS.map((option) => ({ value: option, label: option === 'ALL' ? 'Any status' : option })) },
      { id: 'health', label: 'Health', anyValue: 'ALL', options: PLAYERS_AVAILABILITY_FILTERS.map((option) => ({ value: option, label: option === 'ALL' ? 'Any health' : option })) },
      { id: 'roster', label: 'Roster', anyValue: 'ALL', hidden: !rosterOwnershipKnown, options: PLAYERS_ROSTER_FILTERS.map((option) => ({ value: option, label: option === 'ALL' ? 'Any roster status' : option })) },
      { id: 'sort', label: 'Sort by', anyValue: VALUE_SORT_KEY, options: sortOptions.map((option) => ({ value: option.key, label: option.label })) },
      { id: 'sortMode', label: 'Stat view', anyValue: 'raw', hidden: !activeSortOption.supportsPercentile, options: [{ value: 'raw', label: 'Raw' }, { value: 'percentile', label: 'Percentile' }] },
      { id: 'layout', label: 'Layout', anyValue: 'list', options: [{ value: 'list', label: 'List' }, { value: 'grid', label: 'Grid' }] },
    ],
    [positionOptions, rosterOwnershipKnown, sortOptions, activeSortOption.supportsPercentile],
  );
  const filterValues = useMemo(
    () => valuesFromSingles(filterGroups, { position, age: ageFilter, status: statusFilter, health: availabilityFilter, roster: rosterFilter, sort: activeSortOption.key, sortMode, layout: viewMode }),
    [filterGroups, position, ageFilter, statusFilter, availabilityFilter, rosterFilter, activeSortOption.key, sortMode, viewMode],
  );
  // How many players a draft selection would show, so Apply can say "Show 24 results".
  const filterResultCount = (draft: FilterValues): number | null => {
    const draftPosition = singleValue(filterGroups[0], draft);
    const draftIdp = idpPlayers.length > 0 && isIdpPositionFilter(draftPosition);
    const draftPool = draftIdp ? idpPlayers : offensePool;
    if (!draftPool) return null;
    return filterPlayers(draftPool, {
      search,
      position: draftPosition,
      ageFilter: singleValue(filterGroups[1], draft) as PlayersAgeFilter,
      statusFilter: singleValue(filterGroups[2], draft) as PlayersStatusFilter,
      availabilityFilter: singleValue(filterGroups[3], draft) as PlayersAvailabilityFilter,
      rosterFilter: singleValue(filterGroups[4], draft) as PlayersRosterFilter,
      rosteredPlayerIds,
    }).length;
  };

  const viewSelect = (
    <ViewTabs<(typeof PLAYERS_VIEWS)[number]>
      options={PLAYERS_VIEWS}
      value={tab === 'prospects' ? 'Prospects' : 'Players'}
      onChange={(label) => setTab(label === 'Prospects' ? 'prospects' : 'players')}
      testID="players-view-select"
    />
  );

  return (
    <View style={[styles.container, { paddingTop: headerHeight }]}>
      <GridBackground />
      <PageFamilyTabs family="team" active="players" leagueId={leagueId} leagueName={leagueName} />
      {tab === 'prospects' ? (
        <ScrollView contentContainerStyle={[styles.prospectsContent, { paddingBottom: orbClearance }]}>
          <CollegeScoutingPanel leading={viewSelect} lens={scoutingLens} />
        </ScrollView>
      ) : (
      <>
      <View style={styles.controls}>
        <PageControlRow testID="players-controls">
          {searchOpen ? null : viewSelect}
          <ExpandingSearch value={search} onChange={setSearch} open={searchOpen} onOpenChange={setSearchOpen} label="Search players" placeholder="Search players" />
          {searchOpen ? null : <FilterSheet
            groups={filterGroups}
            values={filterValues}
            showChips={false}
            resultCount={filterResultCount}
            onApply={(next) => {
              setPosition(singleValue(filterGroups[0], next));
              setAgeFilter(singleValue(filterGroups[1], next) as PlayersAgeFilter);
              setStatusFilter(singleValue(filterGroups[2], next) as PlayersStatusFilter);
              setAvailabilityFilter(singleValue(filterGroups[3], next) as PlayersAvailabilityFilter);
              setRosterFilter(singleValue(filterGroups[4], next) as PlayersRosterFilter);
              setSortKey(singleValue(filterGroups[5], next));
              setSortMode(singleValue(filterGroups[6], next) as PlayersSortMode);
              setViewMode(singleValue(filterGroups[7], next) as 'list' | 'grid');
            }}
          />}
        </PageControlRow>
      </View>
      {error ? <ErrorState compact title="Couldn't load players" message={error} onRetry={() => setReloadToken((n) => n + 1)} /> : null}

      {loading ? (
        <SkeletonList label="players" count={7} />
      ) : (
        <ReSettle changeKey={`${activeSortOption.key}:${sortMode}:${sortedPlayers.slice(0, 24).map((p) => p.player_id).join(',')}`}>
        <FlatList
          // Forces a clean remount on toggle — RN's FlatList explicitly does
          // not support changing `numColumns` on the fly (its own invariant
          // warning says to change `key` instead), since the internal row
          // layout math is set up once per mount.
          key={viewMode}
          data={sortedPlayers}
          keyExtractor={(item) => item.player_id}
          extraData={accordionOpenId}
          numColumns={viewMode === 'grid' ? 2 : 1}
          columnWrapperStyle={viewMode === 'grid' ? styles.gridRow : undefined}
          contentContainerStyle={[styles.listContent, { paddingBottom: orbClearance }]}
          initialNumToRender={16}
          maxToRenderPerBatch={16}
          windowSize={9}
          renderItem={renderPlayerItem}
          ListFooterComponent={
            <>
            {picks.length > 0 ? (
              <CompactModule
                id="players.picks"
                title="Draft picks"
                testID="players-picks"
                parts={picksSummaryParts(picks.map((pick) => ({ label: pick.label, season: pick.season ?? null, score: pick.score ?? null })))}
              >
                <PickGroupList
                  picks={picks}
                  renderPick={(pick, isLast) => (
                    <DraftPickAssetRow
                      pickId={pick.pick_id}
                      round={pick.round}
                      label={pick.label}
                      projectedRange={pick.projected_pick_range}
                      pickTier={pick.pick_tier}
                      contextLine={pickProvenance(pick, { showOwner: true })}
                      trailingValue={pick.score != null ? String(Math.round(pick.score)) : '—'}
                      showChevron
                      onPress={() => navigation.navigate('PickDetail', { pick, leagueId, leagueName })}
                      showDivider={!isLast}
                    />
                  )}
                />
              </CompactModule>
            ) : null}
            {sortedPlayers.length > 0 ? (
              <>
                {idpSelected ? <AppText style={styles.idpNote}>{idpMethodNote(idp)}</AppText> : null}
                <AppText style={styles.idpNote}>{"Ranked by value for this league's scoring, roster, and format settings. OVR percentiles a player against others at their position; tap any player for the full breakdown."}</AppText>
                <ValuesCredit freshness={['values', 'injuries']} />
              </>
            ) : null}
            </>
          }
          ListEmptyComponent={
            <EmptyState
              icon="search-outline"
              title="No players match"
              subtitle="Try a different search term or filter combination."
            />
          }
        />
        </ReSettle>
      )}
      </>
      )}
    </View>
  );
}

type PlayerListItemProps = {
  item: RankedPlayer;
  index: number;
  isLast: boolean;
  grid: boolean;
  open: boolean;
  idpConfidence?: string;
  sortFactLabel?: string;
  sortFactValue?: string;
  canAddToTrade: boolean;
  canFindTrades: boolean;
  leagueId: string;
  leagueName: string;
  onToggleRow: (playerId: string) => void;
  onOpenPlayer: (player: RankedPlayer, options: { leagueId: string; leagueName: string }) => void;
  onNavigateTrades: (player: RankedPlayer, initialTab: 'make' | 'search') => void;
};

/**
 * One list row with stable, primitive props. FlatList re-runs renderItem for every
 * row on any parent state change (search text, accordion, sort), so row identity is
 * what has to hold still: handlers are bound here, inside the memo, and the parent
 * passes stable callbacks plus the row's own primitives.
 */
const PlayerListItem = React.memo(function PlayerListItem({
  item, index, isLast, grid, open, idpConfidence, sortFactLabel, sortFactValue, canAddToTrade, canFindTrades, leagueId, leagueName,
  onToggleRow, onOpenPlayer, onNavigateTrades,
}: PlayerListItemProps) {
  return (
    <PlayerRankRow
      idpConfidence={idpConfidence}
      sortFact={sortFactLabel && sortFactValue ? { key: 'sorted-stat', label: sortFactLabel, value: sortFactValue } : null}
      player={item}
      isFirst={index === 0}
      isLast={isLast}
      grid={grid}
      open={open}
      onToggle={() => onToggleRow(item.player_id)}
      onPress={() => onOpenPlayer(item, { leagueId, leagueName })}
      onAddToTrade={canAddToTrade ? () => onNavigateTrades(item, 'make') : undefined}
      onFindTrades={canFindTrades ? () => onNavigateTrades(item, 'search') : undefined}
    />
  );
});

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
  headerButtonRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  container: { flex: 1, backgroundColor: 'transparent' },
  controls: { paddingHorizontal: spacing.lg },
  prospectsContent: { paddingHorizontal: spacing.lg },
  discoveryCard: { marginHorizontal: spacing.lg, marginBottom: spacing.md, gap: spacing.sm },
  // Position/Age/Status/Availability now render as one wrapping row of
  // compact dropdown buttons (FilterDropdownButton) instead of four full
  // rows of always-expanded pills — coridian_, Discord: "these filter pills
  // need to be grouped and turn into drop down menus because this is
  // ridiculous."
  filterRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.xs,
    alignItems: 'center',
  },
  rankingsLabel: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs, paddingHorizontal: spacing.xs },
  rankingsLabelText: { fontSize: 14, fontWeight: '700', color: colors.textSecondary },
  positionRow: { gap: spacing.xs, paddingVertical: 2 },
  positionPill: { minHeight: 44, paddingHorizontal: spacing.lg, alignItems: 'center', justifyContent: 'center', borderRadius: radii.pill, borderWidth: 1, borderColor: colors.borderStrong },
  positionPillOn: { borderColor: colors.accent, backgroundColor: colors.accentMuted },
  positionPillText: { fontSize: 14, fontWeight: '700', color: colors.textPrimary },
  loading: { marginTop: spacing.xl },
  listContent: { paddingHorizontal: spacing.lg, paddingBottom: spacing.xl },
  playerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.glass,
    paddingHorizontal: spacing.md,
    borderLeftWidth: StyleSheet.hairlineWidth * 1.5,
    borderRightWidth: StyleSheet.hairlineWidth * 1.5,
    borderColor: colors.glassBorder,
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
  playerScore: { fontSize: 17, fontWeight: '700', color: colors.accent },
  playerTrailingChips: { flexDirection: 'row', alignItems: 'center', gap: 4, flexWrap: 'wrap', justifyContent: 'flex-end' },
  positionRankPill: {
    backgroundColor: colors.backgroundElevated,
    borderRadius: radii.pill,
    paddingHorizontal: spacing.xs + 2,
    paddingVertical: 1,
  },
  positionRankText: { fontSize: 12, fontWeight: '700', color: colors.textSecondary },
  // Grid (2-up compact card) mode — see PlayerRankRow's `grid` branch.
  // `flex: 1` + a `spacing.sm` column gap so the 2-up gutter matches the
  // vertical gap (the old `width: '48%'` left a ~14pt gutter at phone
  // width); `maxWidth: '50%'` keeps an unpaired last card (odd total count)
  // from stretching to double width.
  gridRow: { gap: spacing.sm, marginBottom: spacing.sm },
  gridCell: { flex: 1, maxWidth: '50%' },
  gridFooterRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: spacing.xs,
    paddingTop: spacing.xs,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.border,
  },
  gridTrailingFooter: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  rowActions: { flexDirection: 'row', alignItems: 'center', gap: 2, paddingLeft: spacing.xs },
  // 40pt tap target (phone layout audit).
  rowActionButton: { width: 44, height: 44, alignItems: 'center', justifyContent: 'center' },
  // Add-to-trade is the row's primary action: accent border + 12% tint (web parity).
  rowActionAccent: { borderWidth: 1, borderColor: colors.accent, borderRadius: radii.sm, backgroundColor: `${colors.accent}1F` },
  idpNote: { fontSize: 12.5, color: colors.textTertiary, textAlign: 'center', marginTop: spacing.sm, paddingHorizontal: spacing.md },
  error: { color: colors.danger, textAlign: 'center', marginHorizontal: spacing.lg, marginBottom: spacing.sm },
  });
}
