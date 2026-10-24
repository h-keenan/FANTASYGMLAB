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
import InsightRow from '../components/InsightRow';
import PortfolioExposurePanel from '../components/PortfolioExposurePanel';
import PortfolioSharePreviewModal from '../components/PortfolioSharePreviewModal';
import ScreenInfoNote from '../components/ScreenInfoNote';
import SegmentedTabBar from '../components/SegmentedTabBar';
import SkeletonBlock from '../components/SkeletonBlock';
import { api, type PortfolioFailedLeague, type PortfolioLeague, type PortfolioSavedLeague } from '../lib/api';
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
import { ESPN_NOT_SUPPORTED, glanceEspnNote } from '../lib/leaguesGlance';
import { queryKeys } from '../lib/queryKeys';
import { toUserErrorMessage } from '../lib/errorMessages';
import { useOrbClearance } from '../lib/orbLayout';
import { useThemeMode } from '../context/ThemeModeContext';
import { radii, spacing, type ThemeColors } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

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
  const espnNote = glanceEspnNote(composed.failedLeagues);
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
            <View style={styles.infoNoteRow}>
              <ScreenInfoNote
                label="Portfolio"
                text="Your standing, record, and top need or opportunity across every saved league — tap a league to open its Dashboard."
              />
              {/* Share waits for every row: a share card of a half-loaded
                  portfolio would silently leave leagues out. */}
              {composed.settled && composed.leagues.length > 0 ? (
                <TouchableOpacity style={styles.shareButton} onPress={() => setShareOpen(true)} hitSlop={8}>
                  <Ionicons name="share-outline" size={14} color={colors.textSecondary} />
                  <AppText style={styles.shareButtonText}>Share</AppText>
                </TouchableOpacity>
              ) : null}
            </View>
            {draftingLeagues.length > 0 ? (
              <DraftingLeaguesNote leagues={draftingLeagues} colors={colors} styles={styles} />
            ) : null}
            {espnNote ? (
              <View style={styles.failedNote}>
                <Ionicons name="information-circle-outline" size={14} color={colors.textSecondary} style={styles.failedNoteIcon} />
                <AppText style={styles.failedNoteText}>{espnNote}</AppText>
              </View>
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
}: {
  leagues: PortfolioFailedLeague[];
  colors: ThemeColors;
  styles: ReturnType<typeof createStyles>;
}) {
  const names = leagues.map((league) => league.league_name).join(', ');
  const plural = leagues.length === 1 ? 'league' : 'leagues';
  return (
    <View style={styles.failedNote}>
      <Ionicons name="time-outline" size={14} color={colors.textSecondary} style={styles.failedNoteIcon} />
      <AppText style={styles.failedNoteText}>
        {`Draft still in progress for ${leagues.length} ${plural}: ${names}. Rosters will show up here once each draft finishes.`}
      </AppText>
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
}: {
  league: PortfolioLeague;
  isFirst: boolean;
  isLast: boolean;
  colors: ThemeColors;
  styles: ReturnType<typeof createStyles>;
  onPress: () => void;
}) {
  const isChampion = league.power_rank === 1;
  const rankColor = isChampion ? colors.premium : colors.accent;
  const record = recordLabel(league);
  const showHealthFlag = Boolean(league.health_flag) && league.health_flag !== 'Stable';
  // Quick-glance signals for this league — value trending down, an injury,
  // a live news story, actionable waiver info, whichever are genuinely true
  // right now (never padded to a fixed count). Falls back to the single
  // top_item for a response that predates top_items.
  const signals = league.top_items?.length ? league.top_items : league.top_item ? [league.top_item] : [];
  const meta = categoryMeta(colors);

  return (
    <FadeInView>
    <TouchableOpacity
      activeOpacity={0.7}
      onPress={onPress}
      style={[
        styles.row,
        isFirst && styles.rowFirst,
        isLast && styles.rowLast,
        !isLast && styles.rowDivider,
      ]}
    >
      <View style={styles.headerRow}>
        <View style={styles.identityGroup}>
          <AppText style={styles.teamName} numberOfLines={1}>
            {league.team_name || 'Unclaimed team'}
          </AppText>
          <AppText style={styles.leagueName} numberOfLines={1}>
            {league.league_name}
          </AppText>
          <View style={styles.metaRow}>
            {record ? <AppText style={styles.record}>{record}</AppText> : null}
            {showHealthFlag ? (
              <View style={styles.healthBadge}>
                <AppText style={styles.healthBadgeText} numberOfLines={1}>
                  {league.health_flag}
                </AppText>
              </View>
            ) : null}
          </View>
        </View>
        {league.power_rank != null ? (
          <View style={[styles.rankPill, isChampion && styles.rankPillFirst, { borderColor: `${rankColor}80` }]}>
            {isChampion ? (
              <Ionicons name="trophy" size={13} color={rankColor} style={styles.rankTrophy} />
            ) : (
              <AppText style={styles.rankLabel}>ROSTER POWER</AppText>
            )}
            <AppText style={[styles.rankValue, { color: rankColor }]}>
              {league.power_rank_tied ? `T-${league.power_rank}` : `#${league.power_rank}`}
            </AppText>
          </View>
        ) : null}
      </View>
      {signals.map((item, index) => {
        const itemMeta = meta[item.category] ?? meta.watch;
        return (
          <InsightRow
            key={item.recommendation_id || `${item.category}-${index}`}
            icon={itemMeta.icon}
            color={itemMeta.color}
            label={itemMeta.label}
            headline={item.headline}
            detail={item.reason}
            last={index === signals.length - 1}
          />
        );
      })}
    </TouchableOpacity>
    </FadeInView>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    root: { flex: 1, backgroundColor: 'transparent' },
    list: { backgroundColor: 'transparent' },
    listContent: { padding: spacing.lg },
    infoNoteWrap: { marginBottom: spacing.md, gap: spacing.sm },
    infoNoteRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
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
    headerRow: { flexDirection: 'row', alignItems: 'flex-start', paddingBottom: spacing.sm },
    identityGroup: { flex: 1, marginRight: spacing.sm },
    teamName: { fontSize: 16, fontWeight: '700', color: colors.textPrimary },
    leagueName: { fontSize: 12, color: colors.textSecondary, marginTop: 1 },
    metaRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs, marginTop: spacing.xs },
    record: { fontSize: 12, fontWeight: '600', color: colors.textSecondary },
    healthBadge: {
      backgroundColor: `${colors.danger}1F`,
      borderRadius: radii.pill,
      paddingHorizontal: spacing.sm,
      paddingVertical: 1,
    },
    healthBadgeText: { fontSize: 10, fontWeight: '700', color: colors.danger },
    rankPill: {
      backgroundColor: colors.background,
      borderRadius: radii.sm,
      borderWidth: 1,
      paddingHorizontal: spacing.sm,
      paddingVertical: 4,
      alignItems: 'center',
      minWidth: 52,
    },
    rankLabel: { fontSize: 9, fontWeight: '700', color: colors.textTertiary, letterSpacing: 0.4 },
    rankValue: { fontSize: 15, fontWeight: '700' },
    rankPillFirst: { backgroundColor: `${colors.premium}1F` },
    rankTrophy: { marginBottom: 1 },
    skeletonGap: { marginTop: spacing.xs },
    skeletonSignals: { gap: spacing.xs, paddingBottom: spacing.md },
  });
}
