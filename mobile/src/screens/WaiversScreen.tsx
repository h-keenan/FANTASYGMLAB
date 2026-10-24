import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  FlatList,
  ScrollView,
  StyleSheet,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import AppText from '../components/AppText';
import SectionHeading from '../components/SectionHeading';
import { useFocusEffect } from '@react-navigation/native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useHeaderHeight } from '@react-navigation/elements';

import AnimatedCard from '../components/AnimatedCard';
import EmptyState from '../components/EmptyState';
import ErrorState from '../components/ErrorState';
import { SkeletonRows } from '../components/SkeletonBlock';
import EvaluationLensHeaderButton from '../components/EvaluationLensHeaderButton';
import FilterDropdownButton from '../components/FilterDropdownButton';
import GmStanceHeaderButton from '../components/GmStanceHeaderButton';
import LeagueSwitcherHeaderButton from '../components/LeagueSwitcherHeaderButton';
import BrandHeaderBar from '../components/BrandHeaderBar';
import GridBackground from '../components/GridBackground';
import OverallRatingBadge from '../components/OverallRatingBadge';
import PlayerIdentityRow from '../components/PlayerIdentityRow';
import PositionBadge from '../components/PositionBadge';
import PremiumLock from '../components/PremiumLock';
import SegmentedTabBar from '../components/SegmentedTabBar';
import DashboardStatRow from '../components/DashboardStatRow';
import PlayerAvatar from '../components/PlayerAvatar';
import ScreenInfoNote from '../components/ScreenInfoNote';
import BeginnerHelp from '../components/BeginnerHelp';
import ViewModeToggle from '../components/ViewModeToggle';
import ValuesCredit from '../components/ValuesCredit';
import WaiverRecommendationCard, {
  waiverInjuryDisplay,
  waiverOpponentContext,
  waiverOpponentContextColor,
  waiverTrendingAddLabel,
} from '../components/WaiverRecommendationCard';
import { api, type WaiverPlayer, type WaiverPriorityAdd } from '../lib/api';
import { bestAvailableCardVisual } from '../lib/bestAvailableCardVisual';
import { toUserErrorMessage } from '../lib/errorMessages';
import { isIdpPositionFilter, withIdpPositionOptions } from '../lib/idpPresentation';
import { filterByRecommendation, type WaiverRecFilter } from '../lib/waiverChips';
import { useOrbClearance } from '../lib/orbLayout';
import { positionRankPrestige } from '../lib/positionRankPrestige';
import { rankedPlayerFromWaiverPlayer } from '../lib/playerStubs';
import { useScreenHeaderTitle } from '../lib/useScreenHeaderTitle';
import { usePlayerListViewMode } from '../lib/viewModePreference';
import { useThemeMode } from '../context/ThemeModeContext';
import { useValuationLens } from '../context/ValuationLensContext';
import { radii, spacing, type ThemeColors } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

type Props = NativeStackScreenProps<RootStackParamList, 'Waivers'>;

// K joins the filter chips alongside the four skill positions — the waiver
// pool already ranks kickers (see BEST_AVAILABLE_POSITIONS and the backend's
// own ["QB","RB","WR","TE","K"] enumeration in modules/waivers_ui.py), it was
// just missing from this chip row. DEF/DST is deliberately left out: the
// waiver pipeline doesn't surface team defenses at all, so a "DEF" chip
// would always render an empty list.
const POSITIONS = ['ALL', 'QB', 'RB', 'WR', 'TE', 'K'];
const BEST_AVAILABLE_POSITIONS = ['QB', 'RB', 'WR', 'TE', 'K'];

type WaiverTab = 'recommended' | 'explore' | 'watchlist';
const TAB_OPTIONS: Array<{ key: WaiverTab; label: string }> = [
  { key: 'recommended', label: 'Recommended' },
  { key: 'explore', label: 'Explore' },
  { key: 'watchlist', label: 'Watchlist' },
];
const REC_FILTER_OPTIONS: Array<{ key: WaiverRecFilter; label: string }> = [
  { key: 'all', label: 'All' },
  { key: 'Add', label: 'Add' },
  { key: 'Stash', label: 'Stash' },
  { key: 'Watch', label: 'Watch' },
];

const NO_LEAGUE_REASONS = new Set([
  'no_sleeper_username_linked',
  'sleeper_user_not_found',
  'not_a_member_of_league',
]);

function reasonMessage(reason: string): string | null {
  if (NO_LEAGUE_REASONS.has(reason)) {
    return "Link your Sleeper account and join this league from Home to see waivers.";
  }
  if (reason === 'empty_roster') {
    return "Your roster in this league looks empty, so there's nothing to weigh adds against yet.";
  }
  if (reason === 'no_player_data') {
    return "Player data isn't available right now — try again in a bit.";
  }
  return null;
}

/** Section header used across every board on this screen — a plain
 * uppercase kicker plus an optional one-line caption underneath, replacing
 * a mix of ad hoc labels so "Priority Adds," "Best Available by Position,"
 * and "All Free Agents" all read as one family of section boundary. */
export default function WaiversScreen({ route, navigation }: Props) {
  const orbClearance = useOrbClearance();
  const headerHeight = useHeaderHeight();
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const { leagueId, leagueName } = route.params;
  const { lens } = useValuationLens(leagueId);
  const [freeAgents, setFreeAgents] = useState<WaiverPlayer[] | null>(null);
  // IDP leagues only; empty otherwise.
  const [idpAgents, setIdpAgents] = useState<WaiverPlayer[]>([]);
  const [priorityAdds, setPriorityAdds] = useState<WaiverPriorityAdd[]>([]);
  const [neededPositions, setNeededPositions] = useState<string[]>([]);
  const [stashCandidates, setStashCandidates] = useState<WaiverPlayer[]>([]);
  const [watchlistCandidates, setWatchlistCandidates] = useState<WaiverPlayer[]>([]);
  const [faabTargets, setFaabTargets] = useState<WaiverPlayer[]>([]);
  const [isPremium, setIsPremium] = useState(true);
  const [stats, setStats] = useState<{ available: number | null; faab: string; faabLabel: string }>({
    available: null,
    faab: '—',
    faabLabel: 'FAAB',
  });
  const [tab, setTab] = useState<WaiverTab>('recommended');
  const [recFilter, setRecFilter] = useState<WaiverRecFilter>('all');
  const [targetIds, setTargetIds] = useState<string[] | null>(null);
  const [targetsFailed, setTargetsFailed] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);
  const [notice, setNotice] = useState<string | null>(null);
  const [position, setPosition] = useState('ALL');
  const [search, setSearch] = useState('');
  const { viewMode, setViewMode } = usePlayerListViewMode('waivers');

  useScreenHeaderTitle(navigation, 'Waivers', leagueName);

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
      (async () => {
        try {
          setError(null);
          const result = await api.getLeagueWaivers(leagueId, { lens, limit: 300 });
          if (cancelled) return;
          setFreeAgents(result.players);
          setIdpAgents(result.idp_players ?? []);
          setPriorityAdds(result.priority_adds);
          setNeededPositions(result.needed_positions);
          setStashCandidates(result.stash_candidates);
          setWatchlistCandidates(result.watchlist_candidates);
          setFaabTargets(result.faab_targets);
          setIsPremium(result.entitlement.is_premium);
          setStats({
            available: result.available_count ?? result.players.length,
            ...(result.faab_enabled === false
              ? { faab: result.waiver_mode === 'reverse_standings' ? 'Reverse' : 'Rolling', faabLabel: 'Waivers' }
              : { faab: result.faab_remaining != null ? `$${result.faab_remaining}` : '—', faabLabel: 'FAAB' }),
          });
          setNotice(result.reason ? reasonMessage(result.reason) : null);
        } catch (err) {
          if (!cancelled) setError(toUserErrorMessage(err, 'Failed to load waivers.'));
        } finally {
          if (!cancelled) setLoading(false);
        }
      })();
      return () => {
        cancelled = true;
      };
    }, [leagueId, lens, reloadToken]),
  );

  const filtered = useMemo(() => {
    if (!freeAgents) return [];
    const query = search.trim().toLowerCase();
    return (isIdpPositionFilter(position) ? idpAgents : freeAgents)
      .filter((p) => position === 'ALL' || p.position === position)
      .filter((p) => !query || (p.name ?? '').toLowerCase().includes(query));
  }, [freeAgents, idpAgents, position, search]);
  const positionOptions = useMemo(() => withIdpPositionOptions(POSITIONS, idpAgents), [idpAgents]);

  // Mirrors modules/waivers_ui.py's render_free_agent_summary_cards: prefer
  // non-stale players with a real score as the pool, falling back to the
  // full free-agent list only if nothing qualifies league-wide (not a
  // per-position fallback) — then the single top scorer per position, plus
  // how many active options exist at that position.
  const bestAvailable = useMemo(() => {
    if (!freeAgents || freeAgents.length === 0) return [];
    const activeAgents = freeAgents.filter((p) => !p.stale_free_agent && (p.score ?? 0) > 0);
    const source = activeAgents.length > 0 ? activeAgents : freeAgents;
    return BEST_AVAILABLE_POSITIONS.map((pos) => {
      const group = source.filter((p) => p.position === pos);
      if (group.length === 0) return null;
      const top = [...group].sort((a, b) => (b.score ?? 0) - (a.score ?? 0))[0];
      return { position: pos, player: top, count: group.length };
    }).filter((entry): entry is { position: string; player: WaiverPlayer; count: number } => entry !== null);
  }, [freeAgents]);

  // Watchlist = the user's GM Targets that are currently free agents here.
  // Fetched lazily the first time the tab opens.
  useEffect(() => {
    if (tab !== 'watchlist' || targetIds !== null) return;
    let cancelled = false;
    api
      .getGmTargets(leagueId)
      .then((result) => {
        if (!cancelled) setTargetIds(result.targets.map((t) => t.player_id));
      })
      .catch(() => {
        if (!cancelled) setTargetsFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, [tab, targetIds, leagueId]);

  const watchlistPlayers = useMemo(() => {
    if (!freeAgents || !targetIds) return [];
    const ids = new Set(targetIds);
    return freeAgents.filter((p) => ids.has(p.player_id));
  }, [freeAgents, targetIds]);

  const openPlayer = useCallback(
    (player: WaiverPlayer) =>
      navigation.navigate('PlayerDetail', { player: rankedPlayerFromWaiverPlayer(player), leagueId, leagueName }),
    [navigation, leagueId, leagueName],
  );

  const topPriority = priorityAdds[0] ?? null;
  const secondaryPriority = priorityAdds.length > 1 ? priorityAdds.slice(1) : [];
  const visibleSecondary = filterByRecommendation(secondaryPriority, recFilter);
  const priorityCaption =
    neededPositions.length > 0
      ? `Personalized for your needs at ${neededPositions.join(', ')}`
      : 'Personalized for your roster';

  return (
    <View style={[styles.container, { paddingTop: headerHeight }]}>
      <GridBackground />
      <BrandHeaderBar leagueId={leagueId} leagueName={leagueName} />
      {/* Recommendation-clarity audit (product-owner ask, this pass): Waivers
          has no in-app waiver-claim/add API (deliberately, see PR #747), so
          "what should I do about this" wasn't answered anywhere on screen —
          a user could reasonably look for an ADD button and not find one.
          Extended this note's body (still tucked behind the ⓘ tap, per brief
          item 17: stays secondary, doesn't interrupt the workflow) to state
          the actual action model once: tap a recommendation for the full
          breakdown, then place the claim in Sleeper — this app never submits
          it for you. */}
      <ScreenInfoNote
        label="How waivers are ranked"
        text={`Free agents ranked for your roster — ordered by fit for ${
          neededPositions.length > 0 ? `your needs at ${neededPositions.join(', ')}` : 'your team'
        }, not just raw value. Tap any recommendation for the full breakdown — that's where you decide. FantasyDesk doesn't submit waiver claims for you; place the claim from your Sleeper league once you've decided.`}
      />
      <View style={styles.headerRow}>
        <AppText style={styles.headerSubtitle}>Ranked by fit for your team.</AppText>
      </View>
      <DashboardStatRow
        style={styles.statRow}
        items={[
          { label: 'Available', value: stats.available != null ? String(stats.available) : '—' },
          { label: stats.faabLabel, value: stats.faab },
          { label: 'Team need', value: neededPositions.length > 0 ? neededPositions.join('/') : 'None' },
        ]}
      />
      <BeginnerHelp term="waiversIntro" style={styles.beginnerIntro} />

      {notice ? <AppText style={styles.notice}>{notice}</AppText> : null}

      <View style={styles.tabWrap}>
        <SegmentedTabBar options={TAB_OPTIONS} active={tab} onChange={setTab} />
      </View>

      {loading ? (
        <SkeletonRows count={6} style={styles.loading} />
      ) : error && !freeAgents ? (
        <ErrorState
          title="Couldn't load waivers"
          message={error}
          onRetry={() => {
            setLoading(true);
            setReloadToken((n) => n + 1);
          }}
        />
      ) : (
        <FlatList
          ListFooterComponent={<ValuesCredit />}
          key={`${tab}-${viewMode}`}
          data={tab === 'explore' ? filtered : tab === 'watchlist' ? watchlistPlayers : []}
          keyExtractor={(item) => item.player_id}
          numColumns={tab === 'explore' && viewMode === 'grid' ? 2 : 1}
          columnWrapperStyle={tab === 'explore' && viewMode === 'grid' ? styles.gridRow : undefined}
          ListHeaderComponent={
            tab === 'recommended' ? (
              <View>
                {topPriority ? (
                  <View style={styles.sectionBlock}>
                    <SectionHeading title="Top Waiver Target" caption={priorityCaption} />
                    <WaiverRecommendationCard
                      player={topPriority}
                      variant="primary"
                      onPress={() => openPlayer(topPriority)}
                    />
                  </View>
                ) : (
                  <AppText style={styles.secondaryCaption}>No waiver option clearly helps right now.</AppText>
                )}
                {secondaryPriority.length > 0 ? (
                  <View style={styles.sectionBlock}>
                    <SectionHeading title="More recommended adds" />
                    <View style={styles.filterPills}>
                      <SegmentedTabBar options={REC_FILTER_OPTIONS} active={recFilter} onChange={setRecFilter} />
                    </View>
                    {visibleSecondary.length === 0 ? (
                      <AppText style={styles.secondaryCaption}>None in this group.</AppText>
                    ) : (
                      <AnimatedCard style={styles.compactGroupCard}>
                        {visibleSecondary.map((player, index) => (
                          <WaiverRecommendationCard
                            key={player.player_id}
                            player={player}
                            variant="compact"
                            rank={index + 2}
                            showDivider={index < visibleSecondary.length - 1}
                            onPress={() => openPlayer(player)}
                          />
                        ))}
                      </AnimatedCard>
                    )}
                  </View>
                ) : null}
                {bestAvailable.length > 0 ? (
                  <View style={styles.sectionBlock}>
                    <SectionHeading title="Position Snapshot" />
                    <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.bestAvailableRow}>
                      {bestAvailable.map(({ position: pos, player, count }) => (
                        <BestAvailableCard
                          key={pos}
                          position={pos}
                          player={player}
                          note={`${count} active`}
                          onPress={() => openPlayer(player)}
                        />
                      ))}
                    </ScrollView>
                  </View>
                ) : null}
                <SecondaryWaiverBoard
                  isPremium={isPremium}
                  stashCandidates={stashCandidates}
                  watchlistCandidates={watchlistCandidates}
                  faabTargets={faabTargets}
                  onPressPlayer={openPlayer}
                />
              </View>
            ) : tab === 'explore' ? (
              <View>
                <View style={styles.discoveryCard}>
                  <TextInput
                    style={styles.searchInput}
                    placeholder="Search free agents"
                    value={search}
                    onChangeText={setSearch}
                    autoCapitalize="none"
                    placeholderTextColor={colors.textTertiary}
                  />
                  <View style={styles.filterRow}>
                    <FilterDropdownButton label="Position" options={positionOptions} value={position} onChange={setPosition} />
                    <ViewModeToggle value={viewMode} onChange={setViewMode} />
                  </View>
                </View>
                <SectionHeading title="All Free Agents" />
              </View>
            ) : (
              <View>
                <SectionHeading title="Your GM Targets on the wire" />
                {targetsFailed ? <AppText style={styles.secondaryCaption}>Couldn't load your GM Targets.</AppText> : null}
                {!targetsFailed && targetIds === null ? <AppText style={styles.secondaryCaption}>Loading…</AppText> : null}
              </View>
            )
          }
          contentContainerStyle={[styles.listContent, { paddingBottom: orbClearance }]}
          renderItem={({ item, index }) => (
            <FreeAgentRow
              player={item}
              rank={index + 1}
              isFirst={index === 0}
              isLast={index === filtered.length - 1}
              grid={viewMode === 'grid'}
              onPress={() => openPlayer(item)}
            />
          )}
          ListEmptyComponent={
            tab === 'explore' ? (
              <EmptyState
                icon="search-outline"
                title="No free agents match"
                subtitle="Try a different search term or position filter."
              />
            ) : tab === 'watchlist' && targetIds !== null && !targetsFailed ? (
              <EmptyState
                icon="bookmark-outline"
                title="No GM Targets on the wire"
                subtitle="None of your GM Targets are free agents right now."
              />
            ) : null
          }
        />
      )}
    </View>
  );
}

// PlayerDetail's route param still expects the /rankings RankedPlayer shape
// (canonical_* ranks); waivers intentionally computes wire-relative ranks
// instead (see api.ts's WaiverPlayer doc comment), so
// rankedPlayerFromWaiverPlayer (lib/playerStubs.ts, shared with League
// Overview's compact Waiver Suggestions section) only forwards the fields
// Quick View actually reads rather than pretending the rank fields mean the
// same thing.

function SecondaryWaiverBoard({
  isPremium,
  stashCandidates,
  watchlistCandidates,
  faabTargets,
  onPressPlayer,
}: {
  isPremium: boolean;
  stashCandidates: WaiverPlayer[];
  watchlistCandidates: WaiverPlayer[];
  faabTargets: WaiverPlayer[];
  onPressPlayer: (player: WaiverPlayer) => void;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  if (!isPremium) {
    return (
      <View style={styles.secondaryLockWrap}>
        <PremiumLock
          title="Full waiver board and FAAB shortlist"
          description="Priority Adds stay free — Premium adds stash candidates, watchlist depth, and a FAAB shortlist so you don't miss the next claim."
        />
      </View>
    );
  }
  if (stashCandidates.length === 0 && watchlistCandidates.length === 0 && faabTargets.length === 0) {
    return null;
  }
  const groups: Array<{ label: string; players: WaiverPlayer[] }> = [
    { label: 'Top Stash Candidates', players: stashCandidates },
    { label: 'Bench Depth', players: watchlistCandidates },
    { label: 'FAAB Shortlist', players: faabTargets },
  ].filter((group) => group.players.length > 0);
  return (
    <View style={styles.secondaryBoard}>
      <ScreenInfoNote
        label="Stash, depth and FAAB: ranked by raw value"
        text="Includes positions you don't currently need, so a higher number here can still rank below a lower one in Priority Adds above. Kickers and defenses are never stash candidates."
      />
      {groups.map((group) => (
        <View key={group.label} style={styles.sectionBlock}>
          <SectionHeading title={group.label} />
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.bestAvailableRow}>
            {group.players.map((player) => (
              <BestAvailableCard
                key={player.player_id}
                position={player.position ?? ''}
                player={player}
                note={player.team ?? undefined}
                onPress={() => onPressPlayer(player)}
              />
            ))}
          </ScrollView>
        </View>
      ))}
    </View>
  );
}

/**
 * coridian_ (Discord, this pass): "we can have the border be the prestige
 * color with a glowing effect, have the name of the prestige along the top,
 * have the overall top right and name bottom center middle. And whatever
 * else." The prestige tier is the same league-wide top-5-at-position
 * gold/silver/bronze banding `OverallRatingBadge`'s crown already uses (see
 * lib/positionRankPrestige.ts) — not a new color system — and the glow
 * treatment is `AnimatedCard`'s own existing `glow`/`glowColor` props (the
 * same mechanism Dashboard's Top Priority card uses), not a bespoke shadow.
 * Only a tiered player gets the colored glow border + label; an untiered
 * player (outside the top 5 at their position) keeps AnimatedCard's normal
 * plain hairline border and shows no label row at all — per
 * UI_MAGNA_CARTA.md §14/§15, the glow/colored-border treatment stays
 * meaningful by not applying to every card uniformly.
 *
 * Per UI_HIERARCHY_DIRECTIVE.md §11 (player identity must outrank badges),
 * the player's name — even though it now sits bottom-center rather than
 * up top — stays the single largest/boldest text on the card
 * (`bestAvailableName`, 15/800) specifically to outweigh the smaller
 * prestige label (10/800, uppercase kicker) and the OVR badge's own tiny
 * text, rather than letting top-of-card placement read as "most important."
 *
 * Feature parity vs. the previous layout: PositionBadge, headshot, numeric
 * score, and the "{count} active" context all still render — only their
 * position within the card changed to make room for the prestige label row
 * and the bottom-center name.
 */
function BestAvailableCard({
  position,
  player,
  note,
  onPress,
}: {
  position: string;
  player: WaiverPlayer;
  note?: string;
  onPress: () => void;
}) {
  const { colors, isDark } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const prestige = positionRankPrestige(player.position_rank, isDark);
  const visual = bestAvailableCardVisual(prestige.tier);
  return (
    <AnimatedCard
      style={styles.bestAvailableCard}
      onPress={onPress}
      glow={visual.glow}
      glowColor={prestige.color ?? undefined}
    >
      <View style={styles.bestAvailableTopRow}>
        {visual.prestigeLabel ? (
          <AppText style={[styles.bestAvailablePrestigeLabel, { color: prestige.color ?? colors.textTertiary }]}>
            {visual.prestigeLabel}
          </AppText>
        ) : (
          <View />
        )}
        <OverallRatingBadge rating={player.overall_rating} positionRank={player.position_rank} />
      </View>
      <PlayerAvatar playerId={player.player_id} size={36} tier={player.tier} style={styles.avatarWrap} />
      {/* Shared PositionBadge (per-position semantic color, e.g. RB green /
          WR blue / TE orange) instead of a flat neutral pill — the concept
          gives each mini-card's position tag a distinct color, and
          PositionBadge is the app's one canonical source for that mapping
          (theme.ts positionColors), already used by every other player row
          on this same screen via PlayerIdentityRow. Wrapped so its own
          alignSelf:'flex-start' doesn't fight this card's centered layout. */}
      <View style={styles.bestAvailablePosBadgeWrap}>
        <PositionBadge position={position} size="sm" />
      </View>
      <AppText style={styles.bestAvailableName} numberOfLines={1}>
        {player.name ?? 'Unknown'}
      </AppText>
      <View style={styles.bestAvailableFooterRow}>
        <AppText style={styles.bestAvailableScore}>{player.score != null ? Math.round(player.score) : '—'}</AppText>
        {note ? <AppText style={styles.bestAvailableCount}>{note}</AppText> : null}
      </View>
    </AnimatedCard>
  );
}

/**
 * Dense free-agent row shared by "All Free Agents" and the secondary
 * Stash/Watchlist/FAAB boards below it — canonical PlayerIdentityRow for
 * identity, a slot chip carrying this list's own rank, and a trailing
 * value/position-rank column. `bare` drops the rank slot + grouped-table
 * edge borders for the secondary board, whose rows already sit inside their
 * own labeled AnimatedCard group rather than a single continuous table.
 *
 * `grid`: coridian_'s 2-up compact card ask (Discord, 2026-10-09) for "All
 * Free Agents" — same PlayerIdentityRow props (`layout="grid"`) and the
 * exact same trailing chip set (score, position rank, OVR), reflowed into a
 * vertical card. Only wired up for the main free-agent list — the small
 * Stash/Watchlist/FAAB boards (`bare`) stay full-width rows inside their own
 * grouped card, where a handful of entries doesn't benefit from a grid.
 */
function FreeAgentRow({
  player,
  rank,
  isFirst,
  isLast,
  bare = false,
  grid = false,
  onPress,
}: {
  player: WaiverPlayer;
  rank: number;
  isFirst: boolean;
  isLast: boolean;
  bare?: boolean;
  grid?: boolean;
  onPress: () => void;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const injury = waiverInjuryDisplay(player.injury_status);
  const contextLine = player.injury_replacement_fit ? player.injury_replacement_note : waiverOpponentContext(player);
  const contextLineColor = player.injury_replacement_fit ? undefined : waiverOpponentContextColor(player, colors);
  const scoreText = player.score != null ? String(Math.round(player.score)) : '—';

  if (grid) {
    return (
      <View style={[styles.gridCell, player.stale_free_agent && styles.freeAgentStale]}>
        <PlayerIdentityRow
          layout="grid"
          playerId={player.player_id}
          name={player.name}
          position={player.position}
          team={player.team}
          tier={player.tier}
          slot={String(rank)}
          injuryLabel={injury.label}
          injuryTone={injury.tone}
          ruledOut={injury.ruledOut}
          contextLine={contextLine}
          contextLineColor={contextLineColor}
          trendingAddLabel={waiverTrendingAddLabel(player)}
          onPress={onPress}
        />
        <TouchableOpacity accessibilityRole="button" onPress={onPress} activeOpacity={0.7} style={styles.gridTrailingFooter}>
          <AppText style={styles.freeAgentValue}>{scoreText}</AppText>
          <View style={styles.freeAgentTrailingChips}>
            {player.position_rank ? (
              <View style={styles.positionRankPill}>
                <AppText style={styles.positionRankText}>
                  {player.position}
                  {player.position_rank}
                </AppText>
              </View>
            ) : null}
            <OverallRatingBadge rating={player.overall_rating} positionRank={player.position_rank} />
          </View>
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <View
      style={[
        bare ? styles.freeAgentRowBare : styles.freeAgentRow,
        !bare && isFirst && styles.freeAgentRowFirst,
        !bare && isLast && styles.freeAgentRowLast,
        !isLast && styles.freeAgentDivider,
        player.stale_free_agent && styles.freeAgentStale,
      ]}
    >
      <View style={styles.freeAgentIdentity}>
        <PlayerIdentityRow
          playerId={player.player_id}
          name={player.name}
          position={player.position}
          team={player.team}
          tier={player.tier}
          slot={bare ? undefined : String(rank)}
          injuryLabel={injury.label}
          injuryTone={injury.tone}
          ruledOut={injury.ruledOut}
          contextLine={contextLine}
          contextLineColor={contextLineColor}
          trendingAddLabel={waiverTrendingAddLabel(player)}
          onPress={onPress}
          showDivider={false}
        />
      </View>
      <TouchableOpacity accessibilityRole="button" onPress={onPress} activeOpacity={0.7} style={styles.freeAgentTrailing}>
        <AppText style={styles.freeAgentValue}>{scoreText}</AppText>
        <View style={styles.freeAgentTrailingChips}>
          {player.position_rank ? (
            <View style={styles.positionRankPill}>
              <AppText style={styles.positionRankText}>
                {player.position}
                {player.position_rank}
              </AppText>
            </View>
          ) : null}
          <OverallRatingBadge rating={player.overall_rating} positionRank={player.position_rank} />
        </View>
      </TouchableOpacity>
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
  headerButtonRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  container: { flex: 1, backgroundColor: 'transparent', paddingTop: spacing.md },
  notice: {
    fontSize: 13,
    color: colors.textSecondary,
    paddingHorizontal: spacing.lg,
    marginBottom: spacing.sm,
    lineHeight: 18,
  },
  discoveryCard: {
    marginHorizontal: spacing.lg,
    marginBottom: spacing.md,
    backgroundColor: colors.glass,
    borderRadius: radii.md,
    borderWidth: StyleSheet.hairlineWidth * 1.5,
    borderColor: colors.glassBorder,
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
  // Position used to be a full row of always-expanded pills — now one
  // compact dropdown button (FilterDropdownButton), matching Players'
  // treatment of the same filter pattern.
  filterRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.xs,
  },
  loading: { marginTop: spacing.xl },
  listContent: { paddingHorizontal: spacing.lg, paddingBottom: spacing.xl },
  sectionBlock: { marginBottom: spacing.lg },
  sectionHeaderWrap: { marginBottom: spacing.sm, gap: 2 },
  sectionLabel: {
    fontSize: 12,
    fontWeight: '700',
    color: colors.textSecondary,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  sectionCaption: { fontSize: 11.5, color: colors.textTertiary },
  compactGroupCard: { marginTop: spacing.sm, padding: spacing.sm },
  bestAvailableRow: { flexDirection: 'row', gap: spacing.sm, paddingRight: spacing.lg },
  bestAvailableCard: {
    width: 124,
    padding: spacing.sm,
    alignItems: 'center',
    gap: 2,
  },
  // Prestige label (left) <-> OVR badge (right). An untiered player renders
  // an empty spacer View in the label's place (rather than omitting the
  // whole row) so `justifyContent: 'space-between'` still pins the OVR
  // badge to the right instead of letting it drift to center/left, and
  // `minHeight` keeps the row from collapsing to 0 for an untiered player
  // with no rating either, so every card in the strip lines up the same.
  bestAvailableTopRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    alignSelf: 'stretch',
    minHeight: 14,
    marginBottom: spacing.xs,
  },
  bestAvailablePrestigeLabel: { fontSize: 10, fontWeight: '800', textTransform: 'uppercase', letterSpacing: 0.5 },
  avatarWrap: { marginRight: spacing.md },
  bestAvailablePosBadgeWrap: { alignSelf: 'center', marginTop: spacing.xs },
  // The most visually dominant text on the card (UI_HIERARCHY_DIRECTIVE.md
  // §11: player identity must outrank badges/chips) — larger and bolder
  // than the prestige label above it and the OVR badge's own text, even
  // though both of those sit higher in the layout.
  bestAvailableName: { fontSize: 15, fontWeight: '800', color: colors.textPrimary, marginTop: spacing.xs },
  bestAvailableFooterRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs, marginTop: 2 },
  bestAvailableScore: { fontSize: 13, fontWeight: '700', color: colors.accent },
  bestAvailableCount: { fontSize: 10, color: colors.textTertiary },
  // No marginTop here (unlike when this board rendered as the list's own
  // ListFooterComponent, trailing the whole page): it now sits directly
  // after Priority Adds' own sectionBlock, which already contributes
  // marginBottom: spacing.lg — an explicit top margin here would double that
  // gap into an oversized empty band between the two personalized-recommendation
  // sections (Magna Carta §7: avoid gaps with no information).
  secondaryLockWrap: { marginTop: 0, marginBottom: spacing.lg },
  secondaryBoard: { marginTop: 0 },
  secondaryCaption: { fontSize: 12, color: colors.textSecondary, lineHeight: 16, marginBottom: spacing.md },
  // Name line first (full width), value + chips on a second line, so names
  // never truncate to "Ja…" on phones.
  freeAgentRow: {
    flexDirection: 'column',
    alignItems: 'stretch',
    backgroundColor: colors.glass,
    paddingHorizontal: spacing.md,
    borderLeftWidth: StyleSheet.hairlineWidth * 1.5,
    borderRightWidth: StyleSheet.hairlineWidth * 1.5,
    borderColor: colors.glassBorder,
  },
  freeAgentRowBare: {
    flexDirection: 'column',
    alignItems: 'stretch',
  },
  freeAgentRowFirst: {
    borderTopWidth: StyleSheet.hairlineWidth * 1.5,
    borderTopLeftRadius: radii.md,
    borderTopRightRadius: radii.md,
  },
  freeAgentRowLast: {
    borderBottomWidth: StyleSheet.hairlineWidth * 1.5,
    borderBottomLeftRadius: radii.md,
    borderBottomRightRadius: radii.md,
  },
  freeAgentDivider: { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border },
  freeAgentStale: { opacity: 0.55 },
  freeAgentIdentity: { alignSelf: 'stretch' },
  freeAgentTrailing: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, paddingLeft: spacing.xs, paddingBottom: spacing.xs },
  freeAgentValue: { fontSize: 16, fontWeight: '700', color: colors.accent },
  beginnerIntro: { paddingHorizontal: spacing.lg, marginBottom: spacing.sm },
  headerRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: spacing.sm,
    paddingHorizontal: spacing.lg,
    marginBottom: spacing.sm,
  },
  statRow: { marginHorizontal: spacing.lg, marginBottom: spacing.md },
  headerSubtitle: { fontSize: 13, color: colors.textSecondary, flexShrink: 1 },
  tabWrap: { paddingHorizontal: spacing.lg, marginBottom: spacing.md },
  filterPills: { marginBottom: spacing.sm },
  freeAgentTrailingChips: { flexDirection: 'row', alignItems: 'center', gap: 4, flexWrap: 'wrap', justifyContent: 'flex-end' },
  positionRankPill: {
    backgroundColor: colors.backgroundElevated,
    borderRadius: radii.pill,
    paddingHorizontal: spacing.xs + 2,
    paddingVertical: 1,
  },
  positionRankText: { fontSize: 10, fontWeight: '700', color: colors.textSecondary },
  // Grid (2-up compact card) mode — see FreeAgentRow's `grid` branch. Same
  // width/space-between approach as PlayersScreen's PlayerRankRow grid cell
  // (keeps an unpaired last card from stretching to double width).
  gridRow: { justifyContent: 'space-between', marginBottom: spacing.sm },
  gridCell: {
    width: '48%',
    backgroundColor: colors.glass,
    borderRadius: radii.md,
    borderWidth: StyleSheet.hairlineWidth * 1.5,
    borderColor: colors.glassBorder,
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
  });
}
