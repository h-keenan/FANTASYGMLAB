import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { FlatList, StyleSheet, TouchableOpacity, View } from 'react-native';
import AppText from '../components/AppText';
import ErrorState from '../components/ErrorState';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useHeaderHeight } from '@react-navigation/elements';
import { Ionicons } from '@expo/vector-icons';
import { useIsRestoring, useQueries, useQuery } from '@tanstack/react-query';

import BrandedSpinner from '../components/BrandedSpinner';
import FadeInView from '../components/FadeInView';
import EmptyState from '../components/EmptyState';
import GridBackground from '../components/GridBackground';
import BriefingItemPlayers from '../components/BriefingItemPlayers';
import TeamAvatar from '../components/TeamAvatar';
import ToneBadge from '../components/ToneBadge';
import SectionHeading from '../components/SectionHeading';
import PortfolioExposurePanel from '../components/PortfolioExposurePanel';
import PortfolioSharePreviewModal from '../components/PortfolioSharePreviewModal';
import SegmentedTabBar from '../components/SegmentedTabBar';
import SkeletonBlock from '../components/SkeletonBlock';
import { api, type DashboardItem, type PortfolioFailedLeague, type PortfolioLeague, type PortfolioSavedLeague } from '../lib/api';
import { portfolioMetadata, showSignalReason, type SignalPlayer } from '../lib/portfolioSignals';
import { composePortfolio, type PortfolioLeagueState } from '../lib/portfolioProgress';
import {
  enabledLeagueIds,
  PORTFOLIO_ROW_MIN_HEIGHT,
  PORTFOLIO_SHELL_SKELETON_COUNT,
  PORTFOLIO_SPLASH_DELAY_MS,
} from '../lib/portfolioLoader';
import { useDelayedFlag } from '../lib/useDelayedFlag';
import { categoryMeta } from '../lib/dashboardItemPresentation';
import { setLastLeague } from '../lib/lastLeague';
import { ESPN_NOT_SUPPORTED } from '../lib/leaguesGlance';
import { queryKeys } from '../lib/queryKeys';
import { toUserErrorMessage } from '../lib/errorMessages';
import { useOrbClearance } from '../lib/orbLayout';
import { useThemeMode } from '../context/ThemeModeContext';
import { radii, spacing, type ThemeColors } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';
import { usePlayerQuickView } from '../context/PlayerQuickViewContext';

type Navigation = NativeStackNavigationProp<RootStackParamList>;

function recordLabel(league: PortfolioLeague): string {
  if (league.wins == null && league.losses == null) return '';
  const base = `${league.wins ?? 0}-${league.losses ?? 0}`;
  return league.ties ? `${base}-${league.ties}` : base;
}

/**
 * coridian_-approved cross-league "Portfolio" view: standing/needs/
 * opportunities across every saved league at once, reusing GET /v1/portfolio
 * (services/mobile_api_service.py), which itself reuses the exact same
 * per-league engine the single-league Dashboard already uses
 * (modules.dashboard_engine.build_league_summary) — this screen adds no new
 * aggregation of its own, just a compact row per league.
 *
 * One continuous grouped surface with internal dividers (Magna Carta §12),
 * not a separately-bordered card per league: each row is a league identity +
 * record/rank header, plus that league's single highest-priority Next Move
 * tile rendered with the shared InsightRow (§28) — the same "top need or
 * opportunity" headline the Dashboard itself leads with, not a new summary.
 * Tapping a row jumps straight into that league's own Dashboard, the same
 * "switch and go manage it" behavior LeagueSwitcherHeaderButton already uses.
 *
 * coridian_, 2026-10-21: "portfolio still takes too long on mobile" — real
 * cause, confirmed by measuring the actual engines this screen's endpoint
 * runs (see the PR for timings): GET /v1/portfolio's own per-league compute
 * is NOT the dominant cost once a request lands (every prior perf pass
 * already fixed the hang-proofing/duplicate-work/cross-worker-caching parts
 * of that). This screen was the one data-fetching screen in the whole app
 * still on the RETIRED hand-rolled `useFocusEffect` fetch pattern (every
 * other screen — Dashboard, MyTeam, Matchup, PlayerDetail, LeagueDetail,
 * Alerts, Recap, Teams — already moved to the shared React Query client,
 * see lib/queryClient.ts) instead of `useQuery`. That meant Portfolio paid
 * a full, uncached GET /v1/portfolio — recomputing every saved league's
 * summary from scratch server-side if its 30s Redis window had lapsed —
 * on EVERY single focus (tab switch, or just backing out of a league's own
 * Dashboard), with no "paint last-known-good instantly, refresh quietly
 * behind it" behavior and no visible refresh indicator: the old data sat
 * frozen on screen for the whole request instead of showing anything was
 * happening. `useQuery` below gives it the exact same cache-first/
 * background-refetch treatment the rest of the app already relies on.
 */
export default function PortfolioScreen() {
  const { openPlayer: openQuickView } = usePlayerQuickView();
  const orbClearance = useOrbClearance();
  const headerHeight = useHeaderHeight();
  const navigation = useNavigation<Navigation>();
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [shareOpen, setShareOpen] = useState(false);
  const [view, setView] = useState<'leagues' | 'exposure'>('leagues');

  // The persisted AsyncStorage cache restores asynchronously — gating on it
  // (same convention as DashboardScreen) keeps this query from firing (and
  // racing/overwriting) before last session's cached response has been
  // hydrated back into the in-memory QueryClient.
  const isRestoring = useIsRestoring();
  // Progressive load (lib/portfolioProgress.ts): the cheap saved-leagues
  // index is the only thing the full-screen spinner waits on; each league's
  // own row is a separate query fired concurrently, so rows replace their
  // skeletons as they arrive instead of the whole screen waiting on the
  // slowest league (and the requests spread across the API's worker
  // processes instead of sharing one).
  const indexQuery = useQuery({
    queryKey: queryKeys.portfolioIndex(),
    queryFn: ({ signal }) => api.getPortfolioIndex(signal),
    enabled: !isRestoring,
  });
  const index = indexQuery.data ?? null;
  const savedLeagues = index?.is_premium ? index.saved_leagues ?? [] : [];
  // At most PORTFOLIO_LEAGUE_CONCURRENCY row queries run at once, in saved
  // order: a row frees its slot once it has fetched this mount (success or
  // error), or if it already holds fresh cached data. Passing React Query's
  // `signal` cancels in-flight rows when the user leaves the screen.
  const [doneIds, setDoneIds] = useState<Record<string, boolean>>({});
  const allowed = enabledLeagueIds(
    savedLeagues.map((league) => league.league_id),
    doneIds,
  );
  const leagueQueries = useQueries({
    queries: savedLeagues.map((league) => ({
      queryKey: queryKeys.portfolioLeague(league.league_id),
      queryFn: ({ signal }: { signal: AbortSignal }) => api.getPortfolioLeague(league.league_id, signal),
      enabled: !isRestoring && allowed.has(league.league_id),
    })),
  });
  const finishedKey = savedLeagues
    .map((league, position) => {
      const query = leagueQueries[position];
      return query && (query.isFetchedAfterMount || (query.data !== undefined && !query.isStale)) ? league.league_id : '';
    })
    .join('|');
  useEffect(() => {
    const finished = finishedKey.split('|').filter(Boolean);
    setDoneIds((prev) => {
      if (finished.every((id) => prev[id])) return prev;
      return { ...prev, ...Object.fromEntries(finished.map((id) => [id, true])) };
    });
  }, [finishedKey]);
  const retryLeague = useCallback(
    (leagueId: string) => {
      const position = savedLeagues.findIndex((league) => league.league_id === leagueId);
      if (position >= 0) void leagueQueries[position]?.refetch();
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [leagueQueries],
  );
  const leagueStates: Record<string, PortfolioLeagueState> = {};
  savedLeagues.forEach((league, position) => {
    const query = leagueQueries[position];
    if (query?.data) leagueStates[league.league_id] = { status: 'success', data: query.data };
    else if (query?.isError) leagueStates[league.league_id] = { status: 'error' };
    else leagueStates[league.league_id] = { status: 'pending' };
  });
  const composed = index ? composePortfolio(index, leagueStates) : null;
  // No index at all yet (neither a persisted cache hit nor a prior in-memory
  // fetch) is the one case that still needs a blank-slate spinner — once
  // any data exists, it paints immediately and a failed background refetch
  // (e.g. a focus refresh after the 30s staleTime window) never blanks it.
  const loading = isRestoring || indexQuery.isPending;
  const error =
    indexQuery.isError && !index
      ? toUserErrorMessage(indexQuery.error, 'Failed to load your portfolio.')
      : null;

  const openLeague = useCallback(
    (league: PortfolioLeague) => {
      void setLastLeague({ leagueId: league.league_id, leagueName: league.league_name });
      navigation.navigate('Dashboard', { leagueId: league.league_id, leagueName: league.league_name });
    },
    [navigation],
  );

  const openPlayer = useCallback(
    (league: PortfolioLeague, player: SignalPlayer) => {
      openQuickView({
          player_id: player.player_id,
          name: player.name,
          position: player.position || null,
          team: player.team || null,
          age: null,
          status: null,
          injury_status: player.injury_status || null,
          tier: player.tier || null,
          score: player.score,
          overall_rank: null,
          position_rank: null,
          rank_unavailable_reason: null,
          opportunity_label: null,
        }, { leagueId: league.league_id, leagueName: league.league_name });
    },
    [navigation],
  );

  // Instant shell (skeleton rows of the final row height); the branded
  // spinner only if the first paint is still empty after the delay, and it
  // goes away the moment the index arrives.
  const showSplash = useDelayedFlag(loading, PORTFOLIO_SPLASH_DELAY_MS);
  if (loading) {
    if (showSplash) return <BrandedSpinner style={[styles.center, { paddingTop: headerHeight }]} />;
    return (
      <View style={[styles.root, { paddingTop: headerHeight }]} testID="portfolio-shell">
        <GridBackground />
        <View style={styles.listContent}>
          {Array.from({ length: PORTFOLIO_SHELL_SKELETON_COUNT }, (_, position) => (
            <PortfolioLeagueSkeleton
              key={position}
              isFirst={position === 0}
              isLast={position === PORTFOLIO_SHELL_SKELETON_COUNT - 1}
              styles={styles}
            />
          ))}
        </View>
      </View>
    );
  }

  if (error) {
    return (
      <View style={[styles.center, { paddingTop: headerHeight }]}>
        <ErrorState title="Couldn't load your portfolio" message={error} onRetry={() => void indexQuery.refetch()} />
      </View>
    );
  }

  if (!index || !composed) return null;

  if (!index.is_premium) {
    return (
      <View style={[styles.root, { paddingTop: headerHeight }]}>
        <GridBackground />
        <EmptyState
          icon="star-outline"
          title={index.upsell?.title ?? 'Portfolio is a Premium feature'}
          subtitle={
            index.upsell?.body ??
            'Upgrade to Premium to see your standing across every saved league in one place.'
          }
          actionLabel="Upgrade to Premium"
          actionVariant="premium"
          onPressAction={() => navigation.navigate('Paywall')}
        />
      </View>
    );
  }

  // coridian_, 2026-10-19: a league stuck mid-draft (Sleeper doesn't assign
  // roster players until the whole draft completes) landed in the same
  // scary "Couldn't load" note as a genuine failure (no linked account,
  // league gone, Sleeper down). Split the two so a drafting league gets a
  // calm, informational note instead.
  const draftingLeagues = composed.failedLeagues.filter((league) => league.reason === 'empty_roster');
  // ESPN leagues have no Portfolio summary yet (modules/espn_leagues.py) —
  // informational, not a failure.
  const espnLeagues = composed.failedLeagues.filter((league) => league.reason === ESPN_NOT_SUPPORTED);
  const realFailedLeagues = composed.failedLeagues.filter(
    (league) => league.reason !== 'empty_roster' && league.reason !== ESPN_NOT_SUPPORTED,
  );
  const rows = composed.rows;

  if (rows.length === 0 && composed.failedLeagues.length === 0) {
    return (
      <View style={[styles.root, { paddingTop: headerHeight }]}>
        <GridBackground />
        <EmptyState
          icon="layers-outline"
          title="No saved leagues yet"
          subtitle="Save a league from Home to see your standing, record, and top need or opportunity across every league here."
          actionLabel="Go to Home"
          onPressAction={() => navigation.navigate('Home')}
        />
      </View>
    );
  }

  return (
    <View style={[styles.root, { paddingTop: headerHeight }]}>
      <GridBackground />
      <FlatList
        style={styles.list}
        contentContainerStyle={[styles.listContent, { paddingBottom: orbClearance }]}
        data={view === 'leagues' ? rows : []}
        keyExtractor={(item) => item.league.league_id}
        ListFooterComponent={view === 'exposure' ? <PortfolioExposurePanel /> : null}
        ListHeaderComponent={
          <View style={styles.infoNoteWrap}>
            <SegmentedTabBar
              options={[
                { key: 'leagues', label: 'Leagues' },
                { key: 'exposure', label: 'Exposure' },
              ]}
              active={view}
              onChange={setView}
            />
            {view === 'leagues' ? (
              <>
            <View style={styles.headerBlock}>
              <View style={styles.headerTop}>
                <View style={styles.headerTitleWrap}>
                  <SectionHeading title="Your leagues" caption="Standing, record, and top need per league." />
                </View>
                {/* Share waits for every row: a share card of a half-loaded
                    portfolio would silently leave leagues out. */}
                {composed.settled && composed.leagues.length > 0 ? (
                  <TouchableOpacity style={styles.shareButton} onPress={() => setShareOpen(true)} hitSlop={8}>
                    <Ionicons name="share-outline" size={14} color={colors.textSecondary} />
                    <AppText style={styles.shareButtonText}>Share</AppText>
                  </TouchableOpacity>
                ) : null}
              </View>
              <TouchableOpacity onPress={() => navigation.navigate('Home')} hitSlop={8} accessibilityRole="link">
                <AppText style={styles.linkText}>+ Add a league</AppText>
              </TouchableOpacity>
            </View>
            {draftingLeagues.length > 0 ? (
              <DraftingLeaguesNote leagues={draftingLeagues} colors={colors} styles={styles} onOpen={(league) => navigation.navigate('LiveDraft', { leagueId: league.league_id, leagueName: league.league_name })} />
            ) : null}
            {espnLeagues.length > 0 ? (
              <EspnLeaguesNote leagues={espnLeagues} colors={colors} styles={styles} onOpen={(league) => navigation.navigate('MyTeam', { leagueId: league.league_id, leagueName: league.league_name })} />
            ) : null}
            {realFailedLeagues.length > 0 ? (
              <FailedLeaguesNote leagues={realFailedLeagues} colors={colors} styles={styles} onRetry={retryLeague} />
            ) : null}
              </>
            ) : null}
          </View>
        }
        renderItem={({ item, index: position }) =>
          item.kind === 'league' ? (
            <PortfolioLeagueCard
              league={item.league}
              isFirst={position === 0}
              isLast={position === rows.length - 1}
              colors={colors}
              styles={styles}
              onPress={() => openLeague(item.league)}
              onPressPlayer={openPlayer}
            />
          ) : (
            <PortfolioLeagueSkeleton
              league={item.league}
              isFirst={position === 0}
              isLast={position === rows.length - 1}
              styles={styles}
            />
          )
        }
      />
      <PortfolioSharePreviewModal
        visible={shareOpen}
        onClose={() => setShareOpen(false)}
        leagues={composed.leagues}
      />
    </View>
  );
}

function DraftingLeaguesNote({
  leagues,
  colors,
  styles,
  onOpen,
}: {
  leagues: PortfolioFailedLeague[];
  colors: ThemeColors;
  styles: ReturnType<typeof createStyles>;
  onOpen: (league: PortfolioFailedLeague) => void;
}) {
  return (
    <View style={styles.failedNote}>
      <Ionicons name="time-outline" size={14} color={colors.textSecondary} style={styles.failedNoteIcon} />
      <View style={styles.noteBody}>
        <AppText style={styles.failedNoteText}>
          {leagues.length === 1 ? 'Draft still in progress:' : 'Drafts still in progress:'} rosters will show up here
          once each draft finishes.
        </AppText>
        {leagues.map((league) => (
          <View key={league.league_id} style={styles.noteLeagueRow}>
            <AppText style={styles.failedNoteText} numberOfLines={1}>
              {league.league_name}
            </AppText>
            <TouchableOpacity onPress={() => onOpen(league)} hitSlop={8} accessibilityRole="link">
              <AppText style={styles.linkTextSmall}>Watch live draft →</AppText>
            </TouchableOpacity>
          </View>
        ))}
      </View>
    </View>
  );
}

/** ESPN leagues have no Portfolio summary yet; same copy and per-league
 * "Open My Team" link as web-next's EspnLeaguesNote. Informational, not a failure. */
function EspnLeaguesNote({
  leagues,
  colors,
  styles,
  onOpen,
}: {
  leagues: PortfolioFailedLeague[];
  colors: ThemeColors;
  styles: ReturnType<typeof createStyles>;
  onOpen: (league: PortfolioFailedLeague) => void;
}) {
  return (
    <View style={styles.failedNote}>
      <Ionicons name="information-circle-outline" size={14} color={colors.textSecondary} style={styles.failedNoteIcon} />
      <View style={styles.noteBody}>
        <AppText style={styles.failedNoteText}>
          Portfolio isn&apos;t available for ESPN leagues yet. Open them from My Team instead.
        </AppText>
        {leagues.map((league) => (
          <View key={league.league_id} style={styles.noteLeagueRow}>
            <AppText style={styles.failedNoteText} numberOfLines={1}>
              {league.league_name}
            </AppText>
            <TouchableOpacity onPress={() => onOpen(league)} hitSlop={8} accessibilityRole="link">
              <AppText style={styles.linkTextSmall}>Open My Team →</AppText>
            </TouchableOpacity>
          </View>
        ))}
      </View>
    </View>
  );
}

function FailedLeaguesNote({
  leagues,
  colors,
  styles,
  onRetry,
}: {
  leagues: PortfolioFailedLeague[];
  colors: ThemeColors;
  styles: ReturnType<typeof createStyles>;
  onRetry?: (leagueId: string) => void;
}) {
  const names = leagues.map((league) => league.league_name).join(', ');
  const plural = leagues.length === 1 ? 'league' : 'leagues';
  return (
    <View style={styles.failedNote}>
      <Ionicons name="alert-circle-outline" size={14} color={colors.textSecondary} style={styles.failedNoteIcon} />
      <AppText style={styles.failedNoteText}>
        {`Couldn't load ${leagues.length} ${plural} right now: ${names}. Everything else below is up to date.`}
      </AppText>
      {onRetry
        ? leagues
            .filter((league) => league.reason === 'unavailable')
            .map((league) => (
              <TouchableOpacity
                key={league.league_id}
                onPress={() => onRetry(league.league_id)}
                hitSlop={8}
                accessibilityRole="button"
                accessibilityLabel={`Retry ${league.league_name}`}
              >
                <AppText style={[styles.failedNoteText, { color: colors.accent, fontWeight: '700' }]}>Retry</AppText>
              </TouchableOpacity>
            ))
        : null}
    </View>
  );
}

/**
 * Placeholder row for a saved league whose summary is still loading —
 * same row container and header layout as PortfolioLeagueCard (identity
 * group + rank pill, then signal lines) so swapping the real row in
 * doesn't visibly jump the list. The league name is real (it comes from
 * the index), so it's shown instead of a bar.
 */
function PortfolioLeagueSkeleton({
  league,
  isFirst,
  isLast,
  styles,
}: {
  league?: PortfolioSavedLeague;
  isFirst: boolean;
  isLast: boolean;
  styles: ReturnType<typeof createStyles>;
}) {
  return (
    <View
      accessibilityLabel={`Loading ${league ? league.league_name : 'your leagues'}`}
      style={[styles.row, isFirst && styles.rowFirst, isLast && styles.rowLast, !isLast && styles.rowDivider]}
    >
      <View style={styles.headerRow}>
        <View style={styles.identityGroup}>
          <SkeletonBlock width="55%" height={18} />
          {league ? (
            <AppText style={styles.leagueName} numberOfLines={1}>
              {league.league_name}
            </AppText>
          ) : (
            <SkeletonBlock width="40%" height={14} style={styles.skeletonGap} />
          )}
          <SkeletonBlock width="25%" height={12} style={styles.skeletonGap} />
        </View>
        <SkeletonBlock width={52} height={38} />
      </View>
      <View style={styles.skeletonSignals}>
        <SkeletonBlock width="85%" height={14} />
        <SkeletonBlock width="65%" height={12} />
        <SkeletonBlock width="80%" height={14} style={styles.skeletonGap} />
        <SkeletonBlock width="60%" height={12} />
      </View>
    </View>
  );
}

function PortfolioLeagueCard({
  league,
  isFirst,
  isLast,
  colors,
  styles,
  onPress,
  onPressPlayer,
}: {
  league: PortfolioLeague;
  isFirst: boolean;
  isLast: boolean;
  colors: ThemeColors;
  styles: ReturnType<typeof createStyles>;
  onPress: () => void;
  onPressPlayer: (league: PortfolioLeague, player: SignalPlayer) => void;
}) {
  const isChampion = league.power_rank === 1;
  const record = recordLabel(league);
  const { showRankBadge, metadata, rankText } = portfolioMetadata(record, league.power_rank, league.power_rank_tied);
  const showHealthFlag = Boolean(league.health_flag) && league.health_flag !== 'Stable';
  // Quick-glance signals for this league: whichever are genuinely true
  // right now (never padded). Falls back to the single top_item for a
  // response that predates top_items.
  const signals = league.top_items?.length ? league.top_items : league.top_item ? [league.top_item] : [];
  const meta = categoryMeta(colors);

  return (
    <FadeInView>
      <View style={[styles.row, isFirst && styles.rowFirst, isLast && styles.rowLast, !isLast && styles.rowDivider]}>
        <TouchableOpacity activeOpacity={0.7} onPress={onPress} accessibilityRole="button">
          <View style={styles.headerRow}>
            {/* Same Sleeper team avatar the website's league card shows. */}
            <TeamAvatar avatarId={league.team_avatar_url} name={league.team_name} size={32} />
            <View style={styles.identityGroup}>
              <AppText style={styles.teamName} numberOfLines={2}>
                {league.team_name || 'Unclaimed team'} — {league.league_name}
              </AppText>
              {metadata ? <AppText style={styles.record}>{metadata}</AppText> : null}
            </View>
            {showRankBadge ? (
              <View style={[styles.rankPill, isChampion && styles.rankPillFirst]}>
                {isChampion ? <Ionicons name="trophy" size={12} color={colors.premium} /> : null}
                <AppText style={[styles.rankValue, { color: colors.premium }]}>{rankText}</AppText>
              </View>
            ) : null}
          </View>
          {showHealthFlag ? (
            <ToneBadge label={league.health_flag} color={colors.danger} size="xs" style={styles.healthBadge} />
          ) : null}
        </TouchableOpacity>
        {signals.length > 0 ? (
          <View>
            {signals.map((item, index) => (
              <PortfolioSignal
                key={item.recommendation_id || `${item.category}-${index}`}
                item={item}
                showDivider={index > 0}
                styles={styles}
                label={(meta[item.category] ?? meta.watch).label}
                color={(meta[item.category] ?? meta.watch).color}
                onPressPlayer={(player) => onPressPlayer(league, player)}
              />
            ))}
          </View>
        ) : (
          <AppText style={styles.emptySignals}>Open this league to see your Next Move.</AppText>
        )}
        <TouchableOpacity onPress={onPress} hitSlop={8} accessibilityRole="link" style={styles.openLink}>
          <AppText style={styles.linkText} numberOfLines={1}>
            Open {league.league_name} Dashboard →
          </AppText>
        </TouchableOpacity>
      </View>
    </FadeInView>
  );
}

/** One quick-glance signal: category pill, headline (+ reason), then the
 * real player identities (headshot, position, tier ring) it names. */
function PortfolioSignal({
  item,
  showDivider,
  label,
  color,
  styles,
  onPressPlayer,
}: {
  item: DashboardItem;
  showDivider: boolean;
  label: string;
  color: string;
  styles: ReturnType<typeof createStyles>;
  onPressPlayer: (player: SignalPlayer) => void;
}) {
  if (!item.headline && !item.reason) return null;
  return (
    <View style={[styles.signal, showDivider && styles.signalDivider]}>
      <View style={styles.signalTextRow}>
        <ToneBadge label={label} color={color} size="xs" />
        <View style={styles.signalText}>
          {item.headline ? <AppText style={styles.signalHeadline}>{item.headline}</AppText> : null}
          {showSignalReason(item) ? <AppText style={styles.signalReason}>{item.reason}</AppText> : null}
        </View>
      </View>
      <BriefingItemPlayers item={item} onPressPlayer={onPressPlayer} />
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    root: { flex: 1, backgroundColor: 'transparent' },
    list: { backgroundColor: 'transparent' },
    listContent: { padding: spacing.lg },
    infoNoteWrap: { marginBottom: spacing.md, gap: spacing.sm },
    headerBlock: { gap: spacing.xs },
    headerTop: { flexDirection: 'row', alignItems: 'flex-start', justifyContent: 'space-between' },
    headerTitleWrap: { flex: 1 },
    linkText: { fontSize: 13, fontWeight: '700', color: colors.accent },
    linkTextSmall: { fontSize: 12, fontWeight: '700', color: colors.accent },
    noteBody: { flex: 1, gap: spacing.xs },
    noteLeagueRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: spacing.sm },
    openLink: { paddingTop: spacing.sm, paddingBottom: spacing.sm },
    emptySignals: { fontSize: 13, color: colors.textTertiary, paddingVertical: spacing.sm },
    signal: { paddingTop: spacing.sm, gap: spacing.xs },
    signalDivider: { marginTop: spacing.sm, borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.hairline },
    signalTextRow: { flexDirection: 'row', alignItems: 'flex-start', gap: spacing.sm },
    signalText: { flex: 1, gap: 2 },
    signalHeadline: { fontSize: 14, fontWeight: '700', color: colors.textPrimary },
    signalReason: { fontSize: 12, color: colors.textSecondary, lineHeight: 16 },
    shareButton: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: 4,
      paddingHorizontal: spacing.sm,
      paddingVertical: 4,
      borderRadius: radii.pill,
      borderWidth: 1,
      borderColor: colors.glassBorder,
    },
    shareButtonText: { fontSize: 12, fontWeight: '600', color: colors.textSecondary },
    center: {
      flex: 1,
      alignItems: 'center',
      justifyContent: 'center',
      padding: spacing.xl,
      backgroundColor: colors.background,
    },
    error: { color: colors.danger, textAlign: 'center' },
    failedNote: {
      flexDirection: 'row',
      alignItems: 'flex-start',
      gap: spacing.xs,
      backgroundColor: colors.badgeBackground,
      borderRadius: radii.sm,
      padding: spacing.sm,
    },
    failedNoteIcon: { marginTop: 1 },
    failedNoteText: { flex: 1, fontSize: 12, color: colors.textSecondary, lineHeight: 16 },
    row: {
      backgroundColor: colors.glass,
      paddingHorizontal: spacing.md,
      paddingTop: spacing.md,
      // Same reserved height for the real row and its skeleton: no jump on fill-in.
      minHeight: PORTFOLIO_ROW_MIN_HEIGHT,
      paddingBottom: spacing.xs,
      marginBottom: spacing.md,
      borderWidth: StyleSheet.hairlineWidth * 1.5,
      borderRadius: radii.md,
      borderColor: colors.glassBorder,
    },
    // Each league is its own module with a gap between, like the website
    // (coridian_, 2026-10-24); kept as no-ops so the call sites stay simple.
    rowFirst: {},
    rowLast: { marginBottom: 0 },
    rowDivider: {},
    headerRow: { flexDirection: 'row', alignItems: 'flex-start', paddingBottom: spacing.xs },
    identityGroup: { flex: 1, marginHorizontal: spacing.sm },
    teamName: { fontSize: 16, fontWeight: '700', color: colors.textPrimary },
    leagueName: { fontSize: 12, color: colors.textSecondary, marginTop: 1 },
    metaRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs, marginTop: spacing.xs },
    record: { fontSize: 12, color: colors.textTertiary, marginTop: spacing.xs },
    healthBadge: { alignSelf: 'flex-start', marginTop: spacing.xs },
    // Top-3 rank pill, same soft gold pill as the website's rank badge.
    rankPill: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: 4,
      backgroundColor: `${colors.premium}1F`,
      borderRadius: radii.pill,
      paddingHorizontal: spacing.sm,
      paddingVertical: 4,
    },
    rankValue: { fontSize: 12, fontWeight: '800' },
    rankPillFirst: {},
    skeletonGap: { marginTop: spacing.xs },
    skeletonSignals: { gap: spacing.xs, paddingBottom: spacing.md },
  });
}
