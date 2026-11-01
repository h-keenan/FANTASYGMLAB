import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { ScrollView, StyleSheet, TouchableOpacity, View } from 'react-native';
import AppText from '../components/AppText';
import ValueStat from '../components/ValueStat';
import EmptyState from '../components/EmptyState';
import { useFocusEffect } from '@react-navigation/native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useHeaderHeight } from '@react-navigation/elements';
import { Ionicons } from '@expo/vector-icons';
import { useIsRestoring, useQuery, useQueryClient } from '@tanstack/react-query';

import AccentCard from '../components/AccentCard';
import AnimatedCard from '../components/AnimatedCard';
import Button from '../components/Button';
import SkeletonBlock, { SkeletonCard } from '../components/SkeletonBlock';
import ErrorState from '../components/ErrorState';
import PushPermissionPrompt from '../components/PushPermissionPrompt';
import CollegeFootballInterestPrompt from '../components/CollegeFootballInterestPrompt';
import EvaluationLensHeaderButton from '../components/EvaluationLensHeaderButton';
import GmStanceHeaderButton from '../components/GmStanceHeaderButton';
import LeagueSwitcherHeaderButton from '../components/LeagueSwitcherHeaderButton';
import GridBackground from '../components/GridBackground';
import IconCircle from '../components/IconCircle';
import InsightRow from '../components/InsightRow';
import PlayerInsightRow from '../components/PlayerInsightRow';
import ExchangeSide from '../components/ExchangeSide';
import RecapReadyCard from '../components/RecapReadyCard';
import TeamAvatar from '../components/TeamAvatar';
import TeamHealthContextBlock, { hasHealthContext } from '../components/TeamHealthContextBlock';
import GuillotineCard from '../components/GuillotineCard';
import LeagueTypeControl from '../components/LeagueTypeControl';
import WeeklyMatchupCard from '../components/WeeklyMatchupCard';
import StorylineSummaryCard from '../components/StorylineSummaryCard';
import WaiverSuggestionsStrip from '../components/WaiverSuggestionsStrip';
import LeagueStandingStrips from '../components/LeagueStandingStrips';
import { rankedPlayerFromWaiverPlayer } from '../lib/playerStubs';
import {
  api,
  type DashboardEntitlementInfo,
  type DashboardItem,
  type DashboardResponse,
  type MatchupResponse,
  type RankedPlayer,
  type TeamRanking,
  type TeamSnapshot,
} from '../lib/api';
import type { SignalPlayer } from '../lib/portfolioSignals';
import { categoryMeta } from '../lib/dashboardItemPresentation';
import MetricCard from '../components/MetricCard';
import PremiumLock from '../components/PremiumLock';
import QuickActionsGrid, { type QuickAction } from '../components/QuickActionsGrid';
import ScreenInfoNote from '../components/ScreenInfoNote';
import FreeLimitNote from '../components/FreeLimitNote';
import GlossaryNote from '../components/GlossaryNote';
import SectionHeading from '../components/SectionHeading';
import BriefingItemPlayers from '../components/BriefingItemPlayers';
import LeaguePulseCard from '../components/LeaguePulseCard';
import { leaguePulseHighlights } from '../lib/leaguePulse';
import TodayHero from '../components/TodayHero';
import StartHereCard from '../components/StartHereCard';
import { useAuth } from '../context/AuthContext';
import BrandHeaderBar from '../components/BrandHeaderBar';
import DashboardGuessCard from '../components/DashboardGuessCard';
import DashboardStatRow from '../components/DashboardStatRow';
import ToneBadge from '../components/ToneBadge';
import { requestOrbSearch } from '../lib/orbEvents';
import { WATCH_TAG_LABEL, usageTrendPct, watchTagKind } from '../lib/dashboardWatch';
import BrandMark from '../components/BrandMark';
import { CONFIDENCE_LEVELS } from '../components/ConfidenceMeter';
import { useOrbClearance } from '../lib/orbLayout';
import { queryKeys } from '../lib/queryKeys';
import { formatRank } from '../lib/percentile';
import { getLastOpenedRecapId } from '../lib/recapSeen';
import { diffAndRecordSeen } from '../lib/sinceLastCheckIn';
import { useScreenHeaderTitle } from '../lib/useScreenHeaderTitle';
import { toUserErrorMessage } from '../lib/errorMessages';
import { isInSeason } from '../lib/seasonPhase';
import { useDensity } from '../context/DensityContext';
import { useExperienceCopy, useExperienceLevel } from '../context/ExperienceLevelContext';
import { DashboardMore, DashboardNowStrip, DashboardTradesBlock } from '../components/DashboardBlocks';
import { isTradeItem, nextMoveRowFilter } from '../lib/dashboardLayout';
import BeginnerHelp from '../components/BeginnerHelp';
import { useThemeMode } from '../context/ThemeModeContext';
import { LINK_HIT_SLOP, radii, spacing, type ThemeColors } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';
import { usePlayerQuickView } from '../context/PlayerQuickViewContext';

type Props = NativeStackScreenProps<RootStackParamList, 'Dashboard'>;
export type DashboardNavigation = Props['navigation'];

// Only destinations mobile can navigate to with just {leagueId, leagueName} —
// "my_team" would need TeamRoster's ownerName/playerIds params, which this
// screen doesn't have on hand, so it's left without a button rather than
// navigating somewhere wrong.
const DESTINATION_BUTTON_LABEL: Record<string, string> = {
  trade_hub: 'Review in Trade Hub',
  waivers: 'Open Waivers',
};
const DESTINATION_ROUTE: Record<string, string> = {
  trade_hub: 'Trades',
  waivers: 'Waivers',
};

/** Player Detail stub for any player a briefing item mentions (web's
 * BriefingItemPlayers chips open that player). */
function playerStubFromSignal(player: SignalPlayer): RankedPlayer {
  return {
    player_id: player.player_id,
    name: player.name || null,
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
  };
}

/** Partitions a dashboard item's route_player_id into the same
 * player-stub shape Player Detail needs to fetch everything else itself —
 * shared by the Hero card and the compact InsightRow rows below it. */
function playerStubFromItem(item: DashboardItem): RankedPlayer {
  return {
    player_id: item.route_player_id,
    name: item.route_player_name || null,
    position: item.route_player_position || null,
    team: item.route_player_team || null,
    age: null,
    status: null,
    injury_status: null,
    tier: item.route_player_tier || null,
    score: item.route_player_score,
    overall_rank: null,
    position_rank: null,
    rank_unavailable_reason: null,
    opportunity_label: null,
  };
}

/** Splits the briefing feed into the three UI_MAGNA_CARTA.md §33 tiers —
 * Top Priority / urgent risks (Watch) / opportunities (Waiver Opportunity +
 * League Movement) — while preserving the server's own within-category
 * ordering. Category is an explicit field already computed server-side
 * (modules.dashboard_workflow); this never re-derives priority itself. */
function groupDashboardItems(items: DashboardItem[]): {
  topPriority: DashboardItem[];
  watch: DashboardItem[];
  opportunity: DashboardItem[];
} {
  const topPriority: DashboardItem[] = [];
  const watch: DashboardItem[] = [];
  const opportunity: DashboardItem[] = [];
  for (const item of items) {
    if (item.category === 'top_priority') topPriority.push(item);
    else if (item.category === 'watch') watch.push(item);
    else opportunity.push(item); // waiver_opportunity, league_movement
  }
  return { topPriority, watch, opportunity };
}

export default function DashboardScreen({ route, navigation }: Props) {
  const { openPlayer: openQuickView } = usePlayerQuickView();
  const orbClearance = useOrbClearance();
  const headerHeight = useHeaderHeight();
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const { session } = useAuth();
  const { leagueId, leagueName } = route.params;
  const [newRecommendationIds, setNewRecommendationIds] = useState<Set<string>>(new Set());
  const [isFirstVisit, setIsFirstVisit] = useState(true);
  const { showExplanations } = useDensity();
  const experienceCopy = useExperienceCopy();
  const { goal } = useExperienceLevel();
  const queryClient = useQueryClient();
  // The persisted AsyncStorage cache restores asynchronously — gating on it
  // keeps a query from firing (and racing/overwriting) before last session's
  // cached response has been hydrated back into the in-memory QueryClient.
  const isRestoring = useIsRestoring();

  // Main dashboard payload — the only one of these three with its own
  // hand-rolled instant-paint cache before this PR (dashboardCache.ts, now
  // retired). `useQuery` gives the exact same "show last-known-good
  // instantly, refresh in background" behavior via the persisted QueryClient
  // for all three fetches below, not just this one.
  const dashboardQuery = useQuery({
    queryKey: queryKeys.dashboard(leagueId),
    queryFn: async () => {
      // Progressive load (mirrors web-next's Dashboard page): a first call
      // without the trade-idea search paints sooner; the full call then
      // replaces it. A cached full response is never overwritten by the
      // lighter first pass, and an empty/quiet first pass is not painted
      // (it would flash the "all quiet" state).
      const firstPass = await api.getLeagueDashboard(leagueId, { deferTradeIdeas: true });
      if (!firstPass.trade_ideas_deferred) return firstPass;
      const key = queryKeys.dashboard(leagueId);
      if (!firstPass.quiet && firstPass.items.length > 0 && !queryClient.getQueryData(key)) {
        queryClient.setQueryData(key, firstPass);
      }
      try {
        return await api.getLeagueDashboard(leagueId);
      } catch (err) {
        if (queryClient.getQueryData(key)) return queryClient.getQueryData(key) as DashboardResponse;
        throw err;
      }
    },
    enabled: !isRestoring,
  });
  // League Pulse's source data — previously fetched fresh on every focus
  // with no cache at all, so this section always showed blank/absent until
  // the request resolved. Now benefits from the same cache-first treatment.
  const teamRankingsQuery = useQuery({
    queryKey: queryKeys.teamRankings(leagueId),
    queryFn: () => api.getLeagueTeamRankings(leagueId),
    enabled: !isRestoring,
  });
  // Weekly Matchup card — same gap as team rankings; also reused verbatim by
  // MatchupScreen (see that screen's own useQuery), so the two screens now
  // share one cache entry under queryKeys.matchup(leagueId) instead of each
  // fetching it independently.
  const matchupQuery = useQuery({
    queryKey: queryKeys.matchup(leagueId),
    queryFn: () => api.getLeagueMatchup(leagueId),
    enabled: !isRestoring,
  });
  const guillotineQuery = useQuery({
    queryKey: queryKeys.guillotine(leagueId),
    queryFn: () => api.getLeagueGuillotine(leagueId),
    enabled: !isRestoring,
  });
  const guillotine = guillotineQuery.data?.is_guillotine ? guillotineQuery.data : null;
  // Backs the "new recap ready" module below — same ready/incomplete gate
  // AlertsScreen's own recap-ready card already uses.
  const recapQuery = useQuery({
    queryKey: queryKeys.recap(leagueId),
    queryFn: () => api.getLeagueRecap(leagueId),
    enabled: !isRestoring,
  });

  // Waiver Suggestions (moved from the retired League Overview): the same
  // Priority Adds the Waivers screen leads with.
  const waiversQuery = useQuery({
    queryKey: queryKeys.waivers(leagueId),
    queryFn: () => api.getLeagueWaivers(leagueId),
    enabled: !isRestoring,
  });
  const priorityAdds = waiversQuery.data?.priority_adds ?? [];

  const dashboardData = dashboardQuery.data;
  const items: DashboardItem[] | null = dashboardData?.items ?? null;
  const teamSnapshot: TeamSnapshot | null = dashboardData?.team_snapshot ?? null;
  const quiet = dashboardData?.quiet ?? false;
  const quietReason = dashboardData?.quiet_reason ?? '';
  const entitlement: DashboardEntitlementInfo | null = dashboardData?.entitlement ?? null;
  const notReadyReason: string | null = dashboardData?.reason || null;
  const teamRankings: TeamRanking[] | null = teamRankingsQuery.data?.teams ?? null;
  const matchup: MatchupResponse | null = matchupQuery.data ?? null;
  // Ready AND not yet opened on this device (lib/recapSeen.ts, by recap_id —
  // see that module's docstring for why id rather than week number) is what
  // makes this a "new, unopened" alert rather than a permanent button —
  // coridian_'s brief. Starts opened=true so a slower AsyncStorage read
  // never flashes the card for a recap this device already saw.
  const readyRecap = recapQuery.data?.recap && !recapQuery.data.recap.incomplete ? recapQuery.data.recap : null;
  const [recapOpened, setRecapOpened] = useState(true);
  useEffect(() => {
    if (!readyRecap) {
      setRecapOpened(true);
      return;
    }
    let cancelled = false;
    (async () => {
      const lastOpenedId = await getLastOpenedRecapId(leagueId);
      if (!cancelled) setRecapOpened(lastOpenedId === readyRecap.recap_id);
    })();
    return () => {
      cancelled = true;
    };
  }, [leagueId, readyRecap?.recap_id]);
  const showRecapModule = readyRecap != null && !recapOpened;

  // No data at all yet (neither a persisted cache hit nor a prior in-memory
  // fetch) — the one case that still needs a blank-slate spinner. Once any
  // data exists, it paints immediately and a failed background refetch below
  // never un-paints it.
  const loading = isRestoring || dashboardQuery.isPending;
  // A background refetch failing after we already have content to show
  // should never blank the whole screen back to an error page — that would
  // defeat the entire point of showing cached data first. Only surface the
  // full-page error when there's truly nothing to show instead.
  const error =
    dashboardQuery.isError && !dashboardData
      ? toUserErrorMessage(dashboardQuery.error, 'Failed to load your Next Move briefing.')
      : null;

  // Diffs each successful dashboard payload's recommendation ids against
  // what this device last saw — same "Since your last check-in" bookkeeping
  // the old useFocusEffect did on every live fetch resolution, now
  // triggered off every successful query resolution (initial or background
  // refetch) instead.
  useEffect(() => {
    if (!dashboardData || dashboardData.reason) return;
    let cancelled = false;
    (async () => {
      const { newIds, isFirstVisit: firstVisit } = await diffAndRecordSeen(
        leagueId,
        dashboardData.items.map((item) => item.recommendation_id),
      );
      if (!cancelled) {
        setNewRecommendationIds(newIds);
        setIsFirstVisit(firstVisit);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [dashboardData, leagueId]);

  useScreenHeaderTitle(navigation, 'Dashboard', leagueName);

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

  // Matches the previous useFocusEffect's cadence (always re-check on
  // regaining focus) but through React Query: invalidating marks each query
  // stale and triggers its background refetch if it's currently mounted —
  // cached data stays on screen throughout, never cleared first.
  useFocusEffect(
    useCallback(() => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.dashboard(leagueId) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.teamRankings(leagueId) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.matchup(leagueId) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.recap(leagueId) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.waivers(leagueId) });
    }, [queryClient, leagueId]),
  );

  if (loading) {
    // Height-reserving skeleton in the loaded screen's order (stat strip,
    // Today card, watchlist rows, activity cards) so nothing jumps on load.
    return (
      <View style={styles.root}>
        <GridBackground />
        <ScrollView
          style={styles.container}
          contentContainerStyle={[styles.content, { paddingBottom: orbClearance, paddingTop: headerHeight }]}
          scrollEnabled={false}
        >
          {/* Same order as the loaded screen: Now chips, Trades, Next moves, My Team, More. */}
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm }}>
            {[0, 1, 2, 3].map((index) => (
              <View key={index} style={{ flexBasis: '48%', flexGrow: 1 }}>
                <SkeletonBlock height={52} radius={radii.md} />
              </View>
            ))}
          </View>
          <SkeletonCard rows={5} />
          <SkeletonCard rows={4} />
          <SkeletonCard rows={3} />
          <SkeletonBlock height={44} radius={radii.md} />
        </ScrollView>
      </View>
    );
  }

  if (error) {
    return (
      <View style={[styles.center, { paddingTop: headerHeight }]}>
        <ErrorState
          title="Couldn't load your briefing"
          message={error}
          onRetry={() => void dashboardQuery.refetch()}
        />
      </View>
    );
  }

  if (notReadyReason) {
    return (
      <View style={[styles.center, { paddingTop: headerHeight }]}>
        <EmptyState icon="time-outline" title="Not ready yet" subtitle={NOT_READY_MESSAGES[notReadyReason] ?? "Couldn't build your Next Move briefing for this league."} />
        <TodayHero
          thisWeek={dashboardData?.this_week}
          leagueId={leagueId}
          leagueName={leagueName}
          onNavigate={(name, params) => (navigation.navigate as (name: string, params?: object) => void)(name, params)}
        />
      </View>
    );
  }

  // `quiet` is a server-side override that suppresses the whole feed (even
  // if `items` technically has entries) in favor of a single steady-state
  // message — same all-or-nothing contract the pre-rebuild screen used, so
  // grouping is computed off an effectively-empty list rather than the raw
  // `items` whenever this is true.
  const showEmptyState = quiet || !items || items.length === 0;
  const grouped = groupDashboardItems(showEmptyState ? [] : items!);
  const navigate = (name: string, params?: object) => (navigation.navigate as (name: string, params?: object) => void)(name, params);
  // The trade idea lives in the Trades block and a "lineup set" row in the Now
  // strip, so the Next moves list never repeats them (lib/dashboardLayout.ts).
  const tradeItems = grouped.topPriority.filter(isTradeItem);
  const nonTradeTopPriority = grouped.topPriority.filter((item) => !isTradeItem(item));
  const nextMovesThisWeek = dashboardData?.this_week
    ? { ...dashboardData.this_week, rows: dashboardData.this_week.rows.filter(nextMoveRowFilter) }
    : dashboardData?.this_week;
  return (
    <View style={styles.root}>
      <GridBackground />
      <ScrollView style={styles.container} contentContainerStyle={[styles.content, { paddingBottom: orbClearance, paddingTop: headerHeight }]}>
      <BrandHeaderBar leagueId={leagueId} leagueName={leagueName} title="Dashboard" onSearch={requestOrbSearch} />
      {/* Module order: lib/dashboardLayout.ts DASHBOARD_MODULE_ORDER (same on web). */}
      {session?.user?.id ? (
        <StartHereCard
          userId={session.user.id}
          accountCreatedAt={session.user.created_at}
          leagueId={leagueId}
          leagueName={leagueName}
          onNavigate={navigate}
        />
      ) : null}

      {dashboardData?.platform_notice ? (
        <AppText style={{ color: colors.textSecondary, fontSize: 12 }}>{dashboardData.platform_notice}</AppText>
      ) : null}

      {dashboardData ? (
        <DashboardNowStrip data={dashboardData} leagueId={leagueId} leagueName={leagueName} onNavigate={navigate} />
      ) : null}

      {dashboardData ? (
        <DashboardTradesBlock
          data={dashboardData}
          tradeItems={tradeItems}
          leagueId={leagueId}
          leagueName={leagueName}
          isBeginner={experienceCopy.isBeginner}
          goal={goal}
          onNavigate={navigate}
          renderTradeCard={(item, index) => (
            <BriefingCard
              key={`trade-${index}`}
              item={item}
              leagueId={leagueId}
              leagueName={leagueName}
              navigation={navigation}
              isNew={newRecommendationIds.has(item.recommendation_id)}
              showExplanations={showExplanations}
              hideAction
            />
          )}
        />
      ) : null}

      {/* Next moves: what is left of the week's plan once the trade idea (Trades
          block) and a "lineup set" row (Now strip) are shown where they belong. */}
      <TodayHero
        thisWeek={nextMovesThisWeek}
        items={nonTradeTopPriority}
        leagueId={leagueId}
        leagueName={leagueName}
        tradePending={false}
        onNavigate={navigate}
        right={
          <TouchableOpacity onPress={() => navigation.navigate('GmPlan', { leagueId, leagueName })} hitSlop={LINK_HIT_SLOP}>
            <AppText style={styles.viewAll}>View All ›</AppText>
          </TouchableOpacity>
        }
        renderCard={(item, index) => (
          <BriefingCard
            key={`top-priority-${index}`}
            item={item}
            leagueId={leagueId}
            leagueName={leagueName}
            navigation={navigation}
            isNew={newRecommendationIds.has(item.recommendation_id)}
            showExplanations={showExplanations}
          />
        )}
        empty={
          <View style={styles.emptyCard}>
            <BrandMark width={120} height={82} />
            <AppText style={styles.emptyText}>
              {quietReason || 'Nothing urgent right now — your roster looks steady.'}
            </AppText>
            {!quietReason ? <BeginnerHelp term="dashboardNothingUrgent" /> : null}
          </View>
        }
      />

      {entitlement ? (
        <FreeLimitNote
          kind="window"
          noun="next moves"
          limit={entitlement.free_limit}
          total={entitlement.visible_count + entitlement.hidden_count}
          shown={entitlement.visible_count}
          isPremium={entitlement.is_premium}
        />
      ) : null}

      {entitlement && !entitlement.is_premium && entitlement.hidden_count > 0 ? (
        <View style={styles.lockWrap}>
          <PremiumLock
            title="More next moves"
            description={`See ${entitlement.hidden_count} more roster, trade, waiver, and health signal${entitlement.hidden_count === 1 ? '' : 's'} so you don't miss the next best move.`}
          />
        </View>
      ) : null}

      {teamSnapshot ? (
        <View style={styles.snapshotSection}>
          <SectionHeading
            title="My Team"
            right={
              <TouchableOpacity onPress={() => navigation.navigate('MyTeam', { leagueId, leagueName })} hitSlop={LINK_HIT_SLOP}>
                <AppText style={styles.viewAll}>Open ›</AppText>
              </TouchableOpacity>
            }
          />
          <DashboardStatStrip snapshot={teamSnapshot} leagueId={leagueId} leagueName={leagueName} navigation={navigation} />
          <TeamSnapshotRow snapshot={teamSnapshot} />
        </View>
      ) : null}

      {guillotine ? <GuillotineCard data={guillotine} /> : null}

      {!isFirstVisit && newRecommendationIds.size > 0 ? (
        <View style={styles.checkInBanner}>
          <Ionicons name="sparkles-outline" size={14} color={colors.accent} />
          <AppText style={styles.checkInText}>
            Since your last check-in: {newRecommendationIds.size} new {newRecommendationIds.size === 1 ? 'item' : 'items'}
          </AppText>
        </View>
      ) : null}

      {/* Watchlist & Alerts, then the Priority Adds the Waivers screen leads with. */}
      <WatchlistAlertsSection
        snapshot={teamSnapshot}
        items={[...grouped.watch, ...grouped.opportunity]}
        leagueId={leagueId}
        leagueName={leagueName}
        navigation={navigation}
        newRecommendationIds={newRecommendationIds}
        showExplanations={showExplanations}
      />
      <WaiverSuggestionsStrip
        adds={priorityAdds}
        onPressPlayer={(player) =>
          openQuickView(rankedPlayerFromWaiverPlayer(player), { leagueId, leagueName })
        }
      />

      {/* Secondary modules stay collapsed behind "More" so the actionable ones
          above are reachable without scrolling past them. */}
      <DashboardMore>
        {teamRankings && leaguePulseHighlights(teamRankings).length > 0 ? (
          <View style={styles.activityRow}>
            {entitlement && !entitlement.is_premium ? (
              <View style={styles.activityCell}>
                <PremiumLock
                  title="League Activity"
                  description="See contender, rebuilder, draft-capital, and activity leaders across the whole league."
                />
              </View>
            ) : (
              <View style={styles.activityCell}>
                <LeaguePulseCard teams={teamRankings} onPress={() => navigation.navigate('Recap', { leagueId, leagueName })} />
              </View>
            )}
          </View>
        ) : null}
        {experienceCopy.isBeginner ? (
          <ScreenInfoNote
            text={`Home base for ${leagueName}: your trades, this week's moves, your team and waiver suggestions, plus quick access to everything else.`}
          />
        ) : null}
        {readyRecap ? (
          <View>
            <SectionHeading title="Storylines" icon="newspaper-outline" />
            <StorylineSummaryCard recap={readyRecap} onPress={() => navigation.navigate('Recap', { leagueId, leagueName })} />
          </View>
        ) : null}
        {showRecapModule && readyRecap ? (
          <RecapReadyCard
            week={readyRecap.week}
            onPress={() => navigation.navigate('Recap', { leagueId, leagueName })}
          />
        ) : null}
        {!guillotine && matchup ? (
          <WeeklyMatchupCard
            matchup={matchup}
            onPress={() => navigation.navigate('Matchup', { leagueId, leagueName })}
          />
        ) : null}
        <View>
          <SectionHeading title="Quick Actions" icon="apps-outline" />
          <DashboardQuickActions
            leagueId={leagueId}
            leagueName={leagueName}
            navigation={navigation}
            // Sleeper's current week off the matchup this screen already
            // loads, bucketed by the same rule as the server's
            // gm_plan.derive_season_phase (lib/seasonPhase.ts) — no dates.
            inSeason={isInSeason(matchup?.week)}
          />
        </View>
        <LeagueTypeControl
          leagueId={leagueId}
          data={guillotineQuery.data}
          onChanged={() => void queryClient.invalidateQueries({ queryKey: queryKeys.guillotine(leagueId) })}
        />
        <DashboardGuessCard />
        <LeagueStandingStrips leagueId={leagueId} onNavigate={navigate} />
      </DashboardMore>

      {/* One-off prompts last: they never sit between the user and the first action. */}
      <CollegeFootballInterestPrompt />
      <PushPermissionPrompt leagueLoaded={!!session?.user?.id && !!dashboardData} />
      </ScrollView>
    </View>
  );
}

const NOT_READY_MESSAGES: Record<string, string> = {
  no_sleeper_username_linked:
    "Link your Sleeper username on the web app first — the Next Move briefing needs to know which roster is yours.",
  sleeper_user_not_found: "Couldn't find that Sleeper account. Double-check the linked username on the web app.",
  not_a_member_of_league: "You don't appear to own a team in this league.",
  empty_roster: "This roster doesn't have any players yet.",
};

// Same icon/color per destination GmOrb's own menu already uses (Trade Hub
// 'shuffle-outline'/premium, Players 'people-outline'/violet, Waivers
// 'swap-horizontal-outline'/success, Draft Center 'albums-outline'/premium)
// — IconCircle's own docstring is "a list of rows scans by color before it
// scans by label," which only holds if the same destination always gets
// the same color everywhere, not a fresh one invented per screen.
//
// Season-aware 4th slot (tap-depth audit #8): during the NFL regular season
// and playoffs it's My Team (lineup / start-sit is the weekly job; shirt
// icon + success green, same as the orb's My Team row) instead of Draft
// Picks, which keeps its orb row and My Team's own draft link. Offseason
// (or no current week known yet) keeps Draft Picks. Same 4 slots either way.
function quickActions(
  colors: ThemeColors,
  inSeason: boolean,
): Array<{
  label: string;
  route: 'Trades' | 'Players' | 'Waivers' | 'DraftCenter' | 'MyTeam' | 'Matchup' | 'Alerts' | 'Teams' | 'GmPlan';
  icon: React.ComponentProps<typeof IconCircle>['name'];
  color: string;
}> {
  return [
    { label: 'Trade Hub', route: 'Trades', icon: 'shuffle-outline', color: colors.premium },
    { label: 'Players', route: 'Players', icon: 'people-outline', color: colors.violet },
    { label: 'Waivers', route: 'Waivers', icon: 'swap-horizontal-outline', color: colors.success },
    inSeason
      ? { label: 'My Team', route: 'MyTeam', icon: 'shirt-outline', color: colors.success }
      : { label: 'Draft Picks', route: 'DraftCenter', icon: 'albums-outline', color: colors.premium },
    // Second row: the League Overview shortcuts (Matchup, Alerts, Teams) now
    // live here, plus the one GM Plan entry. Same icon/color per destination
    // as GmOrb.
    { label: 'Matchup', route: 'Matchup', icon: 'american-football-outline', color: colors.success },
    { label: 'Alerts', route: 'Alerts', icon: 'notifications-outline', color: colors.danger },
    { label: 'League Rankings', route: 'Teams', icon: 'people-circle-outline', color: colors.violet },
    { label: 'GM Plan', route: 'GmPlan', icon: 'map-outline', color: colors.premium },
  ];
}

/** Navigation shortcuts to the app's other hubs — secondary context, not
 * the answer to "what should I do next," so it lives below the actionable
 * feed. Renders through the shared QuickActionsGrid component so any other
 * hub-style screen (League Detail) gets the exact same tile affordance
 * rather than a page-specific reimplementation. */
function DashboardQuickActions({
  leagueId,
  leagueName,
  navigation,
  inSeason,
}: {
  leagueId: string;
  leagueName: string;
  navigation: DashboardNavigation;
  inSeason: boolean;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const actions: QuickAction[] = quickActions(colors, inSeason).map((action) => ({
    key: action.route,
    label: action.label,
    icon: action.icon,
    color: action.color,
    onPress: () => navigation.navigate(action.route, { leagueId, leagueName }),
  }));
  return <QuickActionsGrid actions={actions} style={styles.quickActionsGrid} />;
}

function DestinationButton({
  item,
  leagueId,
  leagueName,
  navigation,
}: {
  item: DashboardItem;
  leagueId: string;
  leagueName: string;
  navigation: DashboardNavigation;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const label = DESTINATION_BUTTON_LABEL[item.destination];
  const routeName = DESTINATION_ROUTE[item.destination];
  if (!label || !routeName) return null;
  return (
    <Button
      variant="secondary"
      style={styles.destButton}
      label={label.toUpperCase()}
      onPress={() => {
        if (!routeName) return;
        (navigation.navigate as (name: string, params?: object) => void)(routeName, { leagueId, leagueName });
      }}
    />
  );
}

/**
 * League Snapshot, rebuilt on MetricCard (the same compact-tile primitive
 * PR #682 introduced for Player Detail's Stats tab) instead of a
 * Dashboard-only tile style — these five metrics are ranks/counts, not
 * percentiles, so MetricCard's percentile prop is simply omitted (it
 * already renders fine as plain label+value in that case). Roster Power/Franchise
 * stay tappable through to Teams; Injuries stays deliberately non-tappable
 * (the Needs Attention section below already carries "the why" when there
 * is one), and gets `valueColor` emphasis when non-zero instead of a
 * one-off danger tile.
 */
export function DashboardStatStrip({
  snapshot,
  leagueId,
  leagueName,
  navigation,
}: {
  snapshot: TeamSnapshot;
  leagueId: string;
  leagueName: string;
  navigation: DashboardNavigation;
}) {
  const record =
    snapshot.wins != null && snapshot.losses != null
      ? `${snapshot.wins}-${snapshot.losses}${snapshot.ties ? `-${snapshot.ties}` : ''}`
      : '—';
  const goToTeams = () => navigation.navigate('Teams', { leagueId, leagueName });
  const copy = useExperienceCopy();
  const averageAgeLabel = copy.label('averageAge', 'Avg Age');
  // Beginner-only term explanations (lib/experienceCopy.ts): empty for
  // advanced/unset accounts, so the strip stays compact.
  const termHelp: Array<[string, string | null]> = copy.isBeginner
    ? [
        ['Power Rank', copy.help('powerRank')],
        ['Franchise Rank', copy.help('franchiseRank')],
        [averageAgeLabel, copy.help('averageAge')],
      ]
    : [];
  return (
    <View>
      <DashboardStatRow
        items={[
          { label: 'Record', icon: 'ribbon-outline', value: record },
          {
            label: 'Power Rank',
            icon: 'trophy-outline',
            value: formatRank(snapshot.power_rank, snapshot.power_rank_tied),
            onPress: goToTeams,
          },
          {
            label: 'Franchise',
            icon: 'shield-outline',
            value: formatRank(snapshot.franchise_rank, snapshot.franchise_rank_tied),
            onPress: goToTeams,
          },
          {
            label: averageAgeLabel,
            icon: 'hourglass-outline',
            value: snapshot.average_age != null ? snapshot.average_age.toFixed(1) : '—',
          },
        ]}
      />
      {termHelp.map(([term, help]) => (
        <BeginnerHelp key={term} text={help ? `${term}: ${help}` : null} />
      ))}
      <GlossaryNote terms={['powerRank', 'franchiseRank', 'averageAge']} />
    </View>
  );
}

/** Starter Strength, Bench Strength and Injuries only; renders under the
 * "My Team" heading together with the record/rank/age strip. */
export function TeamSnapshotRow({ snapshot }: { snapshot: TeamSnapshot }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const copy = useExperienceCopy();
  const injuredCount = snapshot.injured_starters;
  const termHelp: Array<[string, string | null]> = copy.isBeginner
    ? [
        ['Starter Strength', copy.help('starterStrength')],
        ['Bench Strength', copy.help('benchStrength')],
      ]
    : [];
  return (
    <View style={styles.snapshotSection}>
      <DashboardStatRow
        items={[
          {
            label: 'Starter Strength',
            icon: 'link-outline',
            value: snapshot.starter_rank != null ? formatRank(snapshot.starter_rank, !!snapshot.starter_rank_tied) : '—',
          },
          {
            label: 'Bench Strength',
            icon: 'layers-outline',
            value: snapshot.bench_rank != null ? formatRank(snapshot.bench_rank, !!snapshot.bench_rank_tied) : '—',
          },
          {
            label: 'Injuries',
            icon: 'medkit-outline',
            value: injuredCount != null ? (injuredCount > 0 ? String(injuredCount) : 'Stable') : '—',
            valueColor: injuredCount != null && injuredCount > 0 ? colors.danger : undefined,
          },
        ]}
      />
      {termHelp.map(([term, help]) => (
        <BeginnerHelp key={term} text={help ? `${term}: ${help}` : null} style={styles.snapshotHelp} />
      ))}
      <GlossaryNote terms={['starterStrength', 'benchStrength']} />
    </View>
  );
}

function TopPriorityTradeCard({
  item,
  leagueId,
  leagueName,
  navigation,
  isNew,
  showExplanations,
  hideAction = false,
}: {
  item: DashboardItem;
  leagueId: string;
  leagueName: string;
  navigation: DashboardNavigation;
  isNew: boolean;
  showExplanations: boolean;
  /** The Trades block owns the block's one action; hide the card's own button. */
  hideAction?: boolean;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const presentation = item.presentation!;
  const gain = presentation.trade_gain;
  const gainColor = gain > 0 ? colors.successBright : gain < 0 ? colors.danger : colors.textSecondary;
  const gainChipColor = gain > 0 ? colors.successMuted : gain < 0 ? colors.dangerMuted : colors.backgroundElevated;
  const confidenceLevel = CONFIDENCE_LEVELS[presentation.trade_confidence_label?.toLowerCase()] ?? 1;
  const routeName = DESTINATION_ROUTE[item.destination];

  return (
    <AccentCard
      glow
      accent={colors.accent}
      style={styles.card}
      onPress={
        routeName
          ? () => (navigation.navigate as (name: string, params?: object) => void)(routeName, { leagueId, leagueName })
          : undefined
      }
    >
      <View style={styles.cardHeaderRow}>
        <Ionicons name="flash" size={15} color={colors.accent} style={styles.cardIcon} />
        <AppText style={[styles.cardLabel, { color: colors.accent }]}>TOP PRIORITY</AppText>
        {isNew ? <ToneBadge solid size="xs" label="NEW" color={colors.accent} textColor={colors.onAccent} style={{ marginLeft: 4 }} /> : null}
        <ToneBadge label="Trade" icon="swap-horizontal" color={colors.textSecondary} style={styles.tradeBadge} />
      </View>
      <AppText style={styles.cardHeadline}>{presentation.partner_team_name}</AppText>

      <View style={styles.sidesStack}>
        <ExchangeSide side="send" assets={presentation.trade_package.send} />
        <ExchangeSide side="get" assets={presentation.trade_package.receive} />
      </View>

      <View style={styles.valueRow}>
        <View style={[styles.valueChip, { backgroundColor: gainChipColor }]}>
          <ValueStat
            align="flex-start"
            label={`Trade value / ${presentation.trade_market_realism_label}`}
            value={`${gain > 0 ? '+' : ''}${gain}`}
            color={gainColor}
          />
        </View>
      </View>
      <View style={styles.meterRow}>
        <AppText style={styles.meterLabel}>CONFIDENCE</AppText>
        <View style={styles.meterSegments}>
          {[1, 2, 3].map((segment) => (
            <View
              key={segment}
              style={[
                styles.meterSegment,
                { backgroundColor: segment <= confidenceLevel ? colors.accent : colors.borderStrong },
              ]}
            />
          ))}
        </View>
        <AppText style={styles.meterValue}>{presentation.trade_confidence_label}</AppText>
      </View>

      {showExplanations && item.reason ? <AppText style={styles.cardReason}>{item.reason}</AppText> : null}
      {hideAction ? null : <DestinationButton item={item} leagueId={leagueId} leagueName={leagueName} navigation={navigation} />}
    </AccentCard>
  );
}

/** The Hero card for any Top Priority item — trade-shaped ones get the rich
 * send/receive treatment above; anything else (e.g. a "Roster Pressure" or
 * "Injury Alert" tile promoted to top priority with no trade attached)
 * still gets full-card, glow-eligible-by-category emphasis rather than
 * shrinking to an InsightRow, since this is literally the screen's single
 * most important answer. */
export function BriefingCard({
  item,
  leagueId,
  leagueName,
  navigation,
  isNew,
  showExplanations,
  hideAction = false,
}: {
  item: DashboardItem;
  leagueId: string;
  leagueName: string;
  navigation: DashboardNavigation;
  isNew: boolean;
  showExplanations: boolean;
  hideAction?: boolean;
}) {
  const { openPlayer: openQuickView } = usePlayerQuickView();
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  if (item.presentation?.trade_package) {
    return (
      <TopPriorityTradeCard
        item={item}
        leagueId={leagueId}
        leagueName={leagueName}
        navigation={navigation}
        isNew={isNew}
        showExplanations={showExplanations}
        hideAction={hideAction}
      />
    );
  }
  const meta = categoryMeta(colors)[item.category] ?? categoryMeta(colors).watch;
  // A tile that points at exactly one player (e.g. "1 injured starter") used
  // to be a dead end with no way to see who it meant — same lean-player
  // pattern AlertsScreen already uses for its own matched-player taps, since
  // Player Detail fetches everything else itself from player_id.
  const openPlayer = item.route_player_id
    ? () => openQuickView(playerStubFromItem(item), { leagueId, leagueName })
    : undefined;
  return (
    <AccentCard glow accent={meta.color} style={styles.card} onPress={openPlayer}>
      <View style={styles.cardHeaderRow}>
        <Ionicons name={meta.icon} size={15} color={meta.color} style={styles.cardIcon} />
        <AppText style={[styles.cardLabel, { color: meta.color }]}>{meta.label.toUpperCase()}</AppText>
        {isNew ? <ToneBadge solid size="xs" label="NEW" color={colors.accent} textColor={colors.onAccent} style={{ marginLeft: 4 }} /> : null}
        {/* Real signal for why this tile leads the priority ladder (roster
            need > injury pressure > future risk > upgrade opportunity) —
            not a fabricated confidence score, since that ladder is a strict
            step-function. See modules.dashboard_engine.NEED_TIER_LABELS. */}
        {item.tier_label ? (
          <ToneBadge label={item.tier_label} color={colors.textSecondary} style={styles.tradeBadge} />
        ) : null}
      </View>
      <AppText style={styles.cardHeadline}>{item.headline}</AppText>
      {showExplanations && item.reason ? <AppText style={styles.cardReason}>{item.reason}</AppText> : null}
      <BriefingItemPlayers
        item={item}
        onPressPlayer={(player) =>
          openQuickView(playerStubFromSignal(player), { leagueId, leagueName })
        }
      />
      <DestinationButton item={item} leagueId={leagueId} leagueName={leagueName} navigation={navigation} />
    </AccentCard>
  );
}

/** Compact row rendering for a non-hero Watch/Waiver Opportunity/League
 * Movement item — see components/InsightRow.tsx. Preserves every
 * interaction the old per-item AnimatedCard had (player drill-down via row
 * press, destination CTA via the trailing action chip), just at the
 * "short analytical conclusion" visual weight Magna Carta §28 calls for. */
function DashboardInsightRow({
  item,
  leagueId,
  leagueName,
  navigation,
  isNew,
  showExplanations,
  last,
}: {
  item: DashboardItem;
  leagueId: string;
  leagueName: string;
  navigation: DashboardNavigation;
  isNew: boolean;
  showExplanations: boolean;
  last: boolean;
}) {
  const { openPlayer: openQuickView } = usePlayerQuickView();
  const { colors } = useThemeMode();
  const baseMeta = categoryMeta(colors)[item.category] ?? categoryMeta(colors).watch;
  const tagKind = watchTagKind(item);
  const tagColor = tagKind === 'trending' ? colors.danger : tagKind === 'injury' ? colors.premium : tagKind === 'waiver' ? colors.success : baseMeta.color;
  const meta = { ...baseMeta, label: WATCH_TAG_LABEL[tagKind] ?? baseMeta.label, color: tagColor };
  const trendPct = usageTrendPct(item);
  const routeName = DESTINATION_ROUTE[item.destination];
  const actionLabel = DESTINATION_BUTTON_LABEL[item.destination];
  const onActionPress = routeName
    ? () => (navigation.navigate as (name: string, params?: object) => void)(routeName, { leagueId, leagueName })
    : undefined;
  const onPress = item.route_player_id
    ? () => openQuickView(playerStubFromItem(item), { leagueId, leagueName })
    : undefined;

  // Every other player the item names (web shows all of them, not just the
  // route player) via the shared BriefingItemPlayers.
  const playersBlock = (excludePlayerId: string | null) => (
    <BriefingItemPlayers
      item={item}
      excludePlayerId={excludePlayerId}
      onPressPlayer={(player) =>
        openQuickView(playerStubFromSignal(player), { leagueId, leagueName })
      }
    />
  );

  if (item.route_player_id) {
    // Some tiles' headline text IS just the player's own name (e.g. a
    // waiver/trade target) — CompactPlayerModule already renders that
    // identity, so showing it again as a text line would just duplicate it.
    // Other tiles' headline is a real conclusion (e.g. "2 injured
    // starters") that the player module can't express, so that text stays.
    const headlineIsPlayerName =
      item.headline.trim().toLowerCase() === item.route_player_name.trim().toLowerCase();
    return (
      <PlayerInsightRow
        icon={meta.icon}
        color={meta.color}
        label={meta.label}
        headline={headlineIsPlayerName ? null : item.headline}
        isNew={isNew}
        actionLabel={onActionPress ? actionLabel : null}
        onActionPress={onActionPress}
        onPress={onPress}
        last={last}
        playerId={item.route_player_id}
        playerName={item.route_player_name || null}
        position={item.route_player_position || null}
        team={item.route_player_team || null}
        tier={item.route_player_tier || null}
        value={item.route_player_score}
        valueLabel="VALUE"
        detail={showExplanations ? item.reason : null}
        trailing={trendPct !== null ? <ToneBadge label={`↓ ${trendPct}%`} color={colors.danger} /> : null}
      >
        {playersBlock(item.route_player_id)}
      </PlayerInsightRow>
    );
  }

  return (
    <InsightRow
      icon={meta.icon}
      color={meta.color}
      label={meta.label}
      headline={item.headline}
      detail={showExplanations ? item.reason : null}
      isNew={isNew}
      actionLabel={onActionPress ? actionLabel : null}
      onActionPress={onActionPress}
      onPress={onPress}
      last={last}
    >
      {playersBlock(null)}
    </InsightRow>
  );
}

/**
 * Watchlist & Alerts: urgent risks and opportunities as one list. Folds in
 * the team-health block (key injuries) as its leading row. Each row carries a
 * TRENDING / INJURY / WAIVER tag; a trend indicator on the right appears only
 * when the item has a real figure (see lib/dashboardWatch.ts).
 */
export function WatchlistAlertsSection({
  snapshot,
  items,
  leagueId,
  leagueName,
  navigation,
  newRecommendationIds,
  showExplanations,
}: {
  snapshot: TeamSnapshot | null;
  items: DashboardItem[];
  leagueId: string;
  leagueName: string;
  navigation: DashboardNavigation;
  newRecommendationIds: Set<string>;
  showExplanations: boolean;
}) {
  const { openPlayer: openQuickView } = usePlayerQuickView();
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const showHealth = hasHealthContext(snapshot);
  if (!showHealth && items.length === 0) return null;

  // Defensive only: a trade-shaped item should land in top_priority, but if
  // one doesn't it still gets the full send/receive treatment.
  const richItems = items.filter((item) => item.presentation?.trade_package);
  const rowItems = items.filter((item) => !item.presentation?.trade_package);

  return (
    <View style={styles.groupSection}>
      <SectionHeading
        title="Watchlist & Alerts"
        right={
          <TouchableOpacity onPress={() => navigation.navigate('Alerts', { leagueId, leagueName })} hitSlop={LINK_HIT_SLOP}>
            <AppText style={styles.viewAll}>View All ›</AppText>
          </TouchableOpacity>
        }
      />
      {richItems.map((item, index) => (
        <TopPriorityTradeCard
          key={`watch-trade-${index}`}
          item={item}
          leagueId={leagueId}
          leagueName={leagueName}
          navigation={navigation}
          isNew={newRecommendationIds.has(item.recommendation_id)}
          showExplanations={showExplanations}
        />
      ))}
      {showHealth || rowItems.length > 0 ? (
        <AnimatedCard style={styles.groupCard}>
          {showHealth ? (
            <TeamHealthContextBlock
              snapshot={snapshot!}
              last={rowItems.length === 0}
              onPlayerPress={(player) =>
                openQuickView({
                    player_id: player.player_id,
                    name: player.name || null,
                    position: player.position || null,
                    team: player.team || null,
                    age: null,
                    status: null,
                    injury_status: player.injury_status || null,
                    tier: player.tier || null,
                    score: player.player_value_score,
                    overall_rank: null,
                    position_rank: null,
                    rank_unavailable_reason: null,
                    opportunity_label: null,
                  }, { leagueId, leagueName })
              }
            />
          ) : null}
          {rowItems.map((item, index) => (
            <DashboardInsightRow
              key={`watch-${index}`}
              item={item}
              leagueId={leagueId}
              leagueName={leagueName}
              navigation={navigation}
              isNew={newRecommendationIds.has(item.recommendation_id)}
              showExplanations={showExplanations}
              last={index === rowItems.length - 1}
            />
          ))}
        </AnimatedCard>
      ) : null}
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
  headerButtonRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  root: { flex: 1, backgroundColor: 'transparent' },
  container: { flex: 1, backgroundColor: 'transparent' },
  content: { padding: spacing.xl, paddingBottom: spacing.xl * 4 },
  center: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.background,
    padding: spacing.xl,
  },
  disclaimer: { fontSize: 12, color: colors.textSecondary, marginBottom: spacing.lg, lineHeight: 16, textAlign: 'center' },
  // Dashboard's content container has no `gap` (everything else here relies
  // on manual marginBottom), so the shared grid's own spacing is overridden
  // here rather than the grid inventing an opinion about screen spacing —
  // the wrapping `quickActionsSection` (below) now owns that spacing since
  // the grid sits under its own SectionHeading in secondary context.
  quickActionsGrid: { marginBottom: 0 },
  standingStrips: { gap: spacing.md, marginTop: spacing.md },
  quickActionsSection: { marginTop: spacing.lg, marginBottom: spacing.md },
  lockWrap: { marginTop: spacing.md, marginBottom: spacing.md },
  // Shared "grouped surface" wrapper for the Needs Attention / Opportunities
  // tiers — one AnimatedCard containing several InsightRows with internal
  // dividers, per Magna Carta §12, instead of a full card per item.
  groupSection: { marginBottom: spacing.md },
  groupCard: { padding: spacing.lg, paddingVertical: spacing.xs },
  checkInBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
    backgroundColor: colors.accentMuted,
    borderRadius: radii.sm,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    marginBottom: spacing.md,
  },
  checkInText: { fontSize: 12, fontWeight: '600', color: colors.accent, flexShrink: 1 },
  snapshotSection: { marginBottom: spacing.md },
  viewAll: { fontSize: 12, fontWeight: '700', color: colors.accent },
  activityRow: { flexDirection: 'row', gap: spacing.sm, alignItems: 'stretch', marginBottom: spacing.md },
  activityCell: { flex: 1, minWidth: 0 },
  snapshotHelp: { marginTop: spacing.xs },
  snapshotRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.sm,
  },
  // Per-instance MetricCard sizing overrides (Dashboard's League Snapshot
  // only) — see the comment at the call site.
  snapshotTileThird: { minWidth: '30%', flexBasis: '30%' },
  snapshotTileHalf: { minWidth: '48%', flexBasis: '48%' },
  card: { gap: 0, marginBottom: spacing.sm },
  cardHeaderRow: { flexDirection: 'row', alignItems: 'center', marginBottom: spacing.xs },
  cardIcon: { marginRight: spacing.xs },
  cardLabel: { fontSize: 11, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.4 },
  cardHeadline: { fontSize: 16, fontWeight: '700', color: colors.textPrimary, marginBottom: 4 },
  cardReason: { fontSize: 13, color: colors.textSecondary, lineHeight: 18, marginTop: spacing.sm },
  tradeBadge: { marginLeft: 'auto' },
  sidesStack: { gap: spacing.sm, marginTop: spacing.sm },
  valueRow: {
    flexDirection: 'row',
    justifyContent: 'flex-start',
    alignItems: 'center',
    marginTop: spacing.md,
    paddingTop: spacing.sm,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.hairline,
  },
  // A soft tinted chip around the number, not just colored text — "obvious
  // but not sloppy" per coridian_'s brief, so the value result reads as the
  // one clear headline of the row instead of competing with its own label.
  valueChip: {
    borderRadius: radii.pill,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
  },
  meterRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs, marginTop: spacing.md },
  meterLabel: { fontSize: 9, fontWeight: '700', color: colors.textTertiary, letterSpacing: 0.4 },
  meterSegments: { flexDirection: 'row', gap: 3 },
  meterSegment: { width: 18, height: 5, borderRadius: radii.pill },
  meterValue: { fontSize: 11, fontWeight: '600', color: colors.textSecondary },
  destButton: { marginTop: spacing.md, borderColor: colors.accent, paddingVertical: spacing.sm },
  emptyCard: {
    alignItems: 'center',
    padding: spacing.xl,
    gap: spacing.sm,
  },
  emptyText: { fontSize: 14, color: colors.textSecondary, textAlign: 'center', lineHeight: 20 },
  notReadyText: { textAlign: 'center', color: colors.textSecondary, lineHeight: 20 },
  });
}
