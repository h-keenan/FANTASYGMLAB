import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { ScrollView, StyleSheet, TouchableOpacity, View, type ViewStyle } from 'react-native';
import AppText from '../components/AppText';
import { useFocusEffect } from '@react-navigation/native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useHeaderHeight } from '@react-navigation/elements';
import { Ionicons } from '@expo/vector-icons';
import { useIsRestoring, useQuery, useQueryClient } from '@tanstack/react-query';

import AnimatedCard from '../components/AnimatedCard';
import BrandedSpinner from '../components/BrandedSpinner';
import CollegeFootballInterestPrompt from '../components/CollegeFootballInterestPrompt';
import EvaluationLensHeaderButton from '../components/EvaluationLensHeaderButton';
import GmStanceHeaderButton from '../components/GmStanceHeaderButton';
import LeagueSwitcherHeaderButton from '../components/LeagueSwitcherHeaderButton';
import GridBackground from '../components/GridBackground';
import IconCircle from '../components/IconCircle';
import InsightRow from '../components/InsightRow';
import PlayerInsightRow from '../components/PlayerInsightRow';
import NewBadge from '../components/NewBadge';
import PlayerAvatar from '../components/PlayerAvatar';
import PositionBadge from '../components/PositionBadge';
import RecapReadyCard from '../components/RecapReadyCard';
import TeamHealthContextBlock, { hasHealthContext } from '../components/TeamHealthContextBlock';
import WeeklyMatchupCard from '../components/WeeklyMatchupCard';
import {
  api,
  type DashboardEntitlementInfo,
  type DashboardItem,
  type MatchupResponse,
  type PresentationAsset,
  type RankedPlayer,
  type TeamRanking,
  type TeamSnapshot,
} from '../lib/api';
import { categoryMeta } from '../lib/dashboardItemPresentation';
import MetricCard from '../components/MetricCard';
import PremiumLock from '../components/PremiumLock';
import QuickActionsGrid, { type QuickAction } from '../components/QuickActionsGrid';
import ScreenInfoNote from '../components/ScreenInfoNote';
import SectionHeading from '../components/SectionHeading';
import BrandHeaderBar from '../components/BrandHeaderBar';
import BrandMark from '../components/BrandMark';
import { CONFIDENCE_LEVELS } from '../components/ConfidenceMeter';
import { useOrbClearance } from '../lib/orbLayout';
import { queryKeys } from '../lib/queryKeys';
import { formatRank } from '../lib/percentile';
import { getLastOpenedRecapId } from '../lib/recapSeen';
import { diffAndRecordSeen } from '../lib/sinceLastCheckIn';
import { useScreenHeaderTitle } from '../lib/useScreenHeaderTitle';
import { toUserErrorMessage } from '../lib/errorMessages';
import { useDensity } from '../context/DensityContext';
import { useThemeMode } from '../context/ThemeModeContext';
import { radii, spacing, type ThemeColors } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

type Props = NativeStackScreenProps<RootStackParamList, 'Dashboard'>;
type DashboardNavigation = Props['navigation'];

// Only destinations mobile can navigate to with just {leagueId, leagueName} —
// "my_team" would need TeamRoster's ownerName/playerIds params, which this
// screen doesn't have on hand, so it's left without a button rather than
// navigating somewhere wrong.
const DESTINATION_BUTTON_LABEL: Record<string, string> = {
  trade_hub: 'Review in Trade Hub',
  waivers: 'Open Waivers',
};
const DESTINATION_ROUTE: Record<string, string> = {
  trade_hub: 'TradeHub',
  waivers: 'Waivers',
};

interface LeaguePulseTile {
  label: string;
  value: string;
  note: string;
  icon: React.ComponentProps<typeof Ionicons>['name'];
  color: string;
}

function bestByRank(teams: TeamRanking[], rankKey: 'power_rank' | 'draft_capital_rank'): TeamRanking | null {
  let best: TeamRanking | null = null;
  for (const team of teams) {
    const rank = team[rankKey];
    if (rank == null) continue;
    if (best == null || (best[rankKey] ?? Infinity) > rank) best = team;
  }
  return best;
}

function bestByActivity(teams: TeamRanking[]): TeamRanking | null {
  let best: TeamRanking | null = null;
  for (const team of teams) {
    const count = team.transaction_activity_count ?? 0;
    if (count <= 0) continue;
    if (best == null || count > (best.transaction_activity_count ?? 0)) best = team;
  }
  return best;
}

/**
 * A lighter-weight adaptation of the web app's League Pulse
 * (app.py's build_home_league_pulse_items) using only what mobile's
 * /team-rankings endpoint already computes — not a byte-for-byte port.
 * "Most Active Manager" reuses modules.manager_activity's real
 * season-to-date Sleeper transaction scan (trades + waiver claims +
 * free-agent moves), surfaced on /team-rankings as
 * `transaction_activity_count` per roster — see that module's docstring
 * for why this is a pure move count rather than a value read. Web's own
 * Home "Most Active Manager" tile still reads a narrower trade-only count
 * (df_intel's trade_count); unifying the two touches a broadly-shared
 * intelligence frame used across many web features and is a deliberate,
 * separate follow-up rather than something bundled into this mobile-only
 * rebuild (see this PR's description).
 */
function buildLeaguePulseTiles(teams: TeamRanking[], colors: ThemeColors): LeaguePulseTile[] {
  const contenders = teams.filter((t) => t.strategy === 'contender');
  const rebuilders = teams.filter((t) => t.strategy === 'rebuild' || t.strategy === 'tank');
  const contender = bestByRank(contenders, 'power_rank');
  const rebuilder = bestByRank(rebuilders, 'draft_capital_rank');
  const draftLeader = bestByRank(teams, 'draft_capital_rank');
  const mostActive = bestByActivity(teams);

  const tiles: LeaguePulseTile[] = [
    {
      label: 'Biggest Contender',
      value: contender?.team_name ?? 'No clear leader',
      note: contender ? `Power ${formatRank(contender.power_rank, contender.power_rank_tied)}` : 'No contender read available yet.',
      icon: 'flame',
      color: colors.accent,
    },
    {
      label: 'Biggest Rebuilder',
      value: rebuilder?.team_name ?? 'No clear leader',
      note: rebuilder
        ? `Draft Capital ${formatRank(rebuilder.draft_capital_rank, rebuilder.draft_capital_rank_tied)} · ${rebuilder.strategy_label ?? 'Rebuild'}`
        : 'No rebuild read available yet.',
      icon: 'construct',
      color: colors.premium,
    },
    {
      label: 'Draft Capital Leader',
      value: draftLeader?.team_name ?? 'No clear leader',
      note: draftLeader ? `Draft Capital ${formatRank(draftLeader.draft_capital_rank, draftLeader.draft_capital_rank_tied)}` : 'No draft-capital read available yet.',
      icon: 'layers',
      color: colors.success,
    },
    {
      label: 'Most Active Manager',
      value: mostActive?.team_name ?? 'Quiet market',
      note:
        mostActive && mostActive.transaction_activity_count > 0
          ? `${mostActive.transaction_activity_count} move${mostActive.transaction_activity_count === 1 ? '' : 's'} this season`
          : 'No transaction activity tracked yet.',
      icon: 'repeat',
      color: colors.violet,
    },
  ];
  return tiles;
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
  const orbClearance = useOrbClearance();
  const headerHeight = useHeaderHeight();
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const { leagueId, leagueName } = route.params;
  const [newRecommendationIds, setNewRecommendationIds] = useState<Set<string>>(new Set());
  const [isFirstVisit, setIsFirstVisit] = useState(true);
  const { showExplanations } = useDensity();
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
    queryFn: () => api.getLeagueDashboard(leagueId),
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
  // Backs the "new recap ready" module below — same ready/incomplete gate
  // AlertsScreen's own recap-ready card already uses.
  const recapQuery = useQuery({
    queryKey: queryKeys.recap(leagueId),
    queryFn: () => api.getLeagueRecap(leagueId),
    enabled: !isRestoring,
  });

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

  useScreenHeaderTitle(navigation, 'Next Move', leagueName);

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
    }, [queryClient, leagueId]),
  );

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

  if (notReadyReason) {
    return (
      <View style={[styles.center, { paddingTop: headerHeight }]}>
        <AppText style={styles.notReadyText}>
          {NOT_READY_MESSAGES[notReadyReason] ?? "Couldn't build your Next Move briefing for this league."}
        </AppText>
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

  return (
    <View style={styles.root}>
      <GridBackground />
      <ScrollView style={styles.container} contentContainerStyle={[styles.content, { paddingBottom: orbClearance, paddingTop: headerHeight }]}>
      <BrandHeaderBar leagueId={leagueId} leagueName={leagueName} />
      <ScreenInfoNote
        text={`The real Next Move briefing for ${leagueName} — the same roster-pressure, injury, need, and waiver signals the web app's Dashboard uses.`}
      />
      <CollegeFootballInterestPrompt />
      {!isFirstVisit && newRecommendationIds.size > 0 ? (
        <View style={styles.checkInBanner}>
          <Ionicons name="sparkles-outline" size={14} color={colors.accent} />
          <AppText style={styles.checkInText}>
            Since your last check-in: {newRecommendationIds.size} new{' '}
            {newRecommendationIds.size === 1 ? 'item' : 'items'} below
          </AppText>
        </View>
      ) : null}

      {/* HERO — the single answer to "what should I do next?" (Magna Carta
          §33/§4). Everything below this supports it; nothing above it but
          the global header and the tiny "about this screen" affordance. */}
      {showEmptyState ? (
        <View style={styles.emptyCard}>
          <BrandMark width={120} height={82} />
          <AppText style={styles.emptyText}>
            {quietReason || 'Nothing urgent right now — your roster looks steady.'}
          </AppText>
        </View>
      ) : (
        grouped.topPriority.map((item, index) => (
          <BriefingCard
            key={`top-priority-${index}`}
            item={item}
            leagueId={leagueId}
            leagueName={leagueName}
            navigation={navigation}
            isNew={newRecommendationIds.has(item.recommendation_id)}
            showExplanations={showExplanations}
          />
        ))
      )}

      {/* Urgent risks. */}
      <NeedsAttentionSection
        snapshot={teamSnapshot}
        items={grouped.watch}
        leagueId={leagueId}
        leagueName={leagueName}
        navigation={navigation}
        newRecommendationIds={newRecommendationIds}
        showExplanations={showExplanations}
      />

      {/* Opportunities. */}
      <OpportunitiesSection
        items={grouped.opportunity}
        leagueId={leagueId}
        leagueName={leagueName}
        navigation={navigation}
        newRecommendationIds={newRecommendationIds}
        showExplanations={showExplanations}
      />

      {entitlement && !entitlement.is_premium && entitlement.hidden_count > 0 ? (
        <View style={styles.lockWrap}>
          <PremiumLock
            title="More next moves"
            description={`See ${entitlement.hidden_count} more roster, trade, waiver, and health signal${entitlement.hidden_count === 1 ? '' : 's'} so you don't miss the next best move.`}
          />
        </View>
      ) : null}

      {/* Secondary context — useful, but not the answer to "what should I
          do next," so it sits below the actionable feed rather than
          pushing it under the fold. A new, unopened League Recap is a
          one-off alert (coridian_: "should not be a button there... should
          be a module... whenever it's new and has been unopened"), so it
          renders here as the same proven ready-card AlertsScreen already
          uses, not as a permanent nav tile — it disappears the moment this
          device actually opens that recap (see recapOpened above) and
          never dominates the Hero/Needs Attention/Opportunities tiers
          above it (Magna Carta §33). */}
      {showRecapModule && readyRecap ? (
        <RecapReadyCard
          week={readyRecap.week}
          onPress={() => navigation.navigate('Recap', { leagueId, leagueName })}
        />
      ) : null}
      {matchup ? (
        <WeeklyMatchupCard
          matchup={matchup}
          onPress={() => navigation.navigate('Matchup', { leagueId, leagueName })}
        />
      ) : null}
      {teamSnapshot ? (
        <TeamSnapshotRow
          snapshot={teamSnapshot}
          leagueId={leagueId}
          leagueName={leagueName}
          navigation={navigation}
        />
      ) : null}
      <View style={styles.quickActionsSection}>
        <SectionHeading title="Quick Actions" icon="apps-outline" />
        <DashboardQuickActions leagueId={leagueId} leagueName={leagueName} navigation={navigation} />
      </View>
      {teamRankings && teamRankings.length > 0 ? (
        entitlement && !entitlement.is_premium ? (
          <View style={styles.lockWrap}>
            <PremiumLock
              title="Full League Pulse"
              description="See contender, rebuilder, draft-capital, and activity leaders across the whole league."
            />
          </View>
        ) : (
          <LeaguePulseSection teams={teamRankings} />
        )
      ) : null}
      </ScrollView>
    </View>
  );
}

function LeaguePulseSection({ teams }: { teams: TeamRanking[] }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const tiles = buildLeaguePulseTiles(teams, colors);
  return (
    <View style={styles.pulseSection}>
      <SectionHeading title="League Pulse" icon="podium-outline" />
      <View style={styles.pulseGrid}>
        {tiles.map((tile) => (
          <View key={tile.label} style={[styles.pulseTile, { borderLeftColor: tile.color }]}>
            <View style={styles.pulseLabelRow}>
              <Ionicons name={tile.icon} size={12} color={tile.color} />
              <AppText style={[styles.pulseLabel, { color: tile.color }]}>{tile.label.toUpperCase()}</AppText>
            </View>
            <AppText style={styles.pulseValue} numberOfLines={1}>
              {tile.value}
            </AppText>
            <AppText style={styles.pulseNote} numberOfLines={1}>
              {tile.note}
            </AppText>
          </View>
        ))}
      </View>
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
function quickActions(colors: ThemeColors): Array<{
  label: string;
  route: 'TradeHub' | 'Players' | 'Waivers' | 'DraftCenter';
  icon: React.ComponentProps<typeof IconCircle>['name'];
  color: string;
}> {
  return [
    { label: 'Trade Hub', route: 'TradeHub', icon: 'shuffle-outline', color: colors.premium },
    { label: 'Rankings', route: 'Players', icon: 'people-outline', color: colors.violet },
    { label: 'Waivers', route: 'Waivers', icon: 'swap-horizontal-outline', color: colors.success },
    { label: 'Draft Picks', route: 'DraftCenter', icon: 'albums-outline', color: colors.premium },
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
}: {
  leagueId: string;
  leagueName: string;
  navigation: DashboardNavigation;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const actions: QuickAction[] = quickActions(colors).map((action) => ({
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
    <TouchableOpacity
      style={styles.destButton}
      onPress={() => {
        if (!routeName) return;
        (navigation.navigate as (name: string, params?: object) => void)(routeName, { leagueId, leagueName });
      }}
    >
      <AppText style={styles.destButtonText}>{label.toUpperCase()}</AppText>
    </TouchableOpacity>
  );
}

function TradeAssetRow({ asset }: { asset: PresentationAsset }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  if (asset.asset_type === 'pick') {
    return (
      <View style={styles.assetRow}>
        <View style={styles.pickDisc}>
          <Ionicons name="ticket-outline" size={16} color={colors.premium} />
        </View>
        <AppText style={styles.assetName} numberOfLines={1}>
          {asset.label || 'Draft pick'}
        </AppText>
      </View>
    );
  }
  return (
    <View style={styles.assetRow}>
      <PlayerAvatar playerId={asset.player_id} size={32} tier={asset.tier} style={styles.assetAvatar} />
      <View style={styles.assetTextGroup}>
        <AppText style={styles.assetName} numberOfLines={1}>
          {asset.name ?? 'Unknown'}
        </AppText>
        <View style={styles.assetMetaRow}>
          <PositionBadge position={asset.position} />
          <AppText style={styles.assetMeta} numberOfLines={1}>
            {asset.team}
          </AppText>
        </View>
      </View>
    </View>
  );
}

/**
 * League Snapshot, rebuilt on MetricCard (the same compact-tile primitive
 * PR #682 introduced for Player Detail's Stats tab) instead of a
 * Dashboard-only tile style — these five metrics are ranks/counts, not
 * percentiles, so MetricCard's percentile prop is simply omitted (it
 * already renders fine as plain label+value in that case). Power/Franchise
 * stay tappable through to Teams; Injuries stays deliberately non-tappable
 * (the Needs Attention section below already carries "the why" when there
 * is one), and gets `valueColor` emphasis when non-zero instead of a
 * one-off danger tile.
 */
function TeamSnapshotRow({
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
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const record =
    snapshot.wins != null && snapshot.losses != null
      ? `${snapshot.wins}-${snapshot.losses}${snapshot.ties ? `-${snapshot.ties}` : ''}`
      : '—';
  const injuredCount = snapshot.injured_starters;
  const goToTeams = () => navigation.navigate('Teams', { leagueId, leagueName });

  return (
    <View style={styles.snapshotSection}>
      <SectionHeading title="League Snapshot" icon="stats-chart" />
      <View style={styles.snapshotRow}>
        {/* Concept sheet groups these as a 3-up row (Record/Power/Franchise)
         * over a 2-up row (Avg Age/Injuries) rather than an even wrap — a
         * per-instance flexBasis override on MetricCard's existing `style`
         * prop (same override mechanism PR #743 used for PlayerDetail),
         * not a change to MetricCard's own shared default sizing, so no
         * other MetricCard consumer is affected. */}
        <MetricCard label="Record" icon="ribbon-outline" value={record} style={styles.snapshotTileThird} />
        {snapshot.power_rank != null ? (
          <MetricCard
            label="Power"
            icon="flash"
            value={formatRank(snapshot.power_rank, snapshot.power_rank_tied)}
            onPress={goToTeams}
            style={styles.snapshotTileThird}
          />
        ) : null}
        {snapshot.franchise_rank != null ? (
          <MetricCard
            label="Franchise"
            icon="star"
            value={formatRank(snapshot.franchise_rank, snapshot.franchise_rank_tied)}
            onPress={goToTeams}
            style={styles.snapshotTileThird}
          />
        ) : null}
        <MetricCard
          label="Avg Age"
          icon="hourglass-outline"
          value={snapshot.average_age != null ? snapshot.average_age.toFixed(1) : '—'}
          style={styles.snapshotTileHalf}
        />
        <MetricCard
          label="Injuries"
          icon="medkit-outline"
          value={injuredCount != null ? String(injuredCount) : '—'}
          valueColor={injuredCount != null && injuredCount > 0 ? colors.danger : undefined}
          style={styles.snapshotTileHalf}
        />
      </View>
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
}: {
  item: DashboardItem;
  leagueId: string;
  leagueName: string;
  navigation: DashboardNavigation;
  isNew: boolean;
  showExplanations: boolean;
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
    <AnimatedCard
      glow
      style={StyleSheet.flatten([styles.card, { borderLeftColor: colors.accent } as ViewStyle])}
      onPress={
        routeName
          ? () => (navigation.navigate as (name: string, params?: object) => void)(routeName, { leagueId, leagueName })
          : undefined
      }
    >
      <View style={styles.cardHeaderRow}>
        <Ionicons name="flash" size={15} color={colors.accent} style={styles.cardIcon} />
        <AppText style={[styles.cardLabel, { color: colors.accent }]}>TOP PRIORITY</AppText>
        {isNew ? <NewBadge /> : null}
        <View style={styles.tradeBadge}>
          <Ionicons name="swap-horizontal" size={12} color={colors.textSecondary} />
          <AppText style={styles.tradeBadgeText}>TRADE</AppText>
        </View>
      </View>
      <AppText style={styles.cardHeadline}>{presentation.partner_team_name}</AppText>

      <View style={styles.sideBlock}>
        <View style={[styles.sideBar, { backgroundColor: colors.danger }]} />
        <View style={styles.sideContent}>
          <AppText style={styles.sideLabel}>YOU GIVE</AppText>
          {presentation.trade_package.send.map((asset, index) => (
            <TradeAssetRow key={`send-${index}`} asset={asset} />
          ))}
        </View>
      </View>
      <View style={styles.sideBlock}>
        <View style={[styles.sideBar, { backgroundColor: colors.successBright }]} />
        <View style={styles.sideContent}>
          <AppText style={styles.sideLabel}>YOU GET</AppText>
          {presentation.trade_package.receive.map((asset, index) => (
            <TradeAssetRow key={`receive-${index}`} asset={asset} />
          ))}
        </View>
      </View>

      <View style={styles.valueRow}>
        <AppText style={styles.valueLabel}>
          TRADE VALUE / {presentation.trade_market_realism_label.toUpperCase()}
        </AppText>
        <View style={[styles.valueChip, { backgroundColor: gainChipColor }]}>
          <AppText style={[styles.valueNumber, { color: gainColor }]}>
            {gain > 0 ? '+' : ''}
            {gain}
          </AppText>
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
      <DestinationButton item={item} leagueId={leagueId} leagueName={leagueName} navigation={navigation} />
    </AnimatedCard>
  );
}

/** The Hero card for any Top Priority item — trade-shaped ones get the rich
 * send/receive treatment above; anything else (e.g. a "Roster Pressure" or
 * "Injury Alert" tile promoted to top priority with no trade attached)
 * still gets full-card, glow-eligible-by-category emphasis rather than
 * shrinking to an InsightRow, since this is literally the screen's single
 * most important answer. */
function BriefingCard({
  item,
  leagueId,
  leagueName,
  navigation,
  isNew,
  showExplanations,
}: {
  item: DashboardItem;
  leagueId: string;
  leagueName: string;
  navigation: DashboardNavigation;
  isNew: boolean;
  showExplanations: boolean;
}) {
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
      />
    );
  }
  const meta = categoryMeta(colors)[item.category] ?? categoryMeta(colors).watch;
  // A tile that points at exactly one player (e.g. "1 injured starter") used
  // to be a dead end with no way to see who it meant — same lean-player
  // pattern AlertsScreen already uses for its own matched-player taps, since
  // Player Detail fetches everything else itself from player_id.
  const openPlayer = item.route_player_id
    ? () => navigation.navigate('PlayerDetail', { player: playerStubFromItem(item), leagueId, leagueName })
    : undefined;
  return (
    <AnimatedCard
      glow
      style={StyleSheet.flatten([styles.card, { borderLeftColor: meta.color } as ViewStyle])}
      onPress={openPlayer}
    >
      <View style={styles.cardHeaderRow}>
        <Ionicons name={meta.icon} size={15} color={meta.color} style={styles.cardIcon} />
        <AppText style={[styles.cardLabel, { color: meta.color }]}>{meta.label.toUpperCase()}</AppText>
        {isNew ? <NewBadge /> : null}
        {/* Real signal for why this tile leads the priority ladder (roster
            need > injury pressure > future risk > upgrade opportunity) —
            not a fabricated confidence score, since that ladder is a strict
            step-function. See modules.dashboard_engine.NEED_TIER_LABELS. */}
        {item.tier_label ? (
          <View style={styles.tradeBadge}>
            <AppText style={styles.tradeBadgeText}>{item.tier_label.toUpperCase()}</AppText>
          </View>
        ) : null}
      </View>
      <AppText style={styles.cardHeadline}>{item.headline}</AppText>
      {showExplanations && item.reason ? <AppText style={styles.cardReason}>{item.reason}</AppText> : null}
      <DestinationButton item={item} leagueId={leagueId} leagueName={leagueName} navigation={navigation} />
    </AnimatedCard>
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
  const { colors } = useThemeMode();
  const meta = categoryMeta(colors)[item.category] ?? categoryMeta(colors).watch;
  const routeName = DESTINATION_ROUTE[item.destination];
  const actionLabel = DESTINATION_BUTTON_LABEL[item.destination];
  const onActionPress = routeName
    ? () => (navigation.navigate as (name: string, params?: object) => void)(routeName, { leagueId, leagueName })
    : undefined;
  const onPress = item.route_player_id
    ? () => navigation.navigate('PlayerDetail', { player: playerStubFromItem(item), leagueId, leagueName })
    : undefined;

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
      />
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
    />
  );
}

/**
 * "Urgent risks" tier of the Next Move hierarchy (Magna Carta §33: Top
 * Priority -> urgent risks -> opportunities -> secondary context). Folds
 * the old standalone injury-detail card in as this group's leading block —
 * same information, no longer a separate bordered card sitting apart from
 * the Watch items it elaborates on.
 */
function NeedsAttentionSection({
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
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const showHealth = hasHealthContext(snapshot);
  if (!showHealth && items.length === 0) return null;

  // Defensive only: category assignment is server-side, and a trade-shaped
  // item should always land in top_priority in practice — but if one ever
  // doesn't, it still gets the full send/receive treatment rather than
  // being squeezed into a two-line row that would drop its trade package.
  const richItems = items.filter((item) => item.presentation?.trade_package);
  const rowItems = items.filter((item) => !item.presentation?.trade_package);

  return (
    <View style={styles.groupSection}>
      <SectionHeading title="Needs Attention" icon="eye-outline" />
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
                navigation.navigate('PlayerDetail', {
                  player: {
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
                  },
                  leagueId,
                  leagueName,
                })
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

/** "Opportunities" tier — Waiver Opportunity + League Movement items. */
function OpportunitiesSection({
  items,
  leagueId,
  leagueName,
  navigation,
  newRecommendationIds,
  showExplanations,
}: {
  items: DashboardItem[];
  leagueId: string;
  leagueName: string;
  navigation: DashboardNavigation;
  newRecommendationIds: Set<string>;
  showExplanations: boolean;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  if (items.length === 0) return null;
  const richItems = items.filter((item) => item.presentation?.trade_package);
  const rowItems = items.filter((item) => !item.presentation?.trade_package);

  return (
    <View style={styles.groupSection}>
      <SectionHeading title="Opportunities" icon="swap-horizontal-outline" />
      {richItems.map((item, index) => (
        <TopPriorityTradeCard
          key={`opportunity-trade-${index}`}
          item={item}
          leagueId={leagueId}
          leagueName={leagueName}
          navigation={navigation}
          isNew={newRecommendationIds.has(item.recommendation_id)}
          showExplanations={showExplanations}
        />
      ))}
      {rowItems.length > 0 ? (
        <AnimatedCard style={styles.groupCard}>
          {rowItems.map((item, index) => (
            <DashboardInsightRow
              key={`opportunity-${index}`}
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
  root: { flex: 1, backgroundColor: colors.background },
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
  quickActionsSection: { marginTop: spacing.lg, marginBottom: spacing.md },
  lockWrap: { marginTop: spacing.md, marginBottom: spacing.md },
  // Shared "grouped surface" wrapper for the Needs Attention / Opportunities
  // tiers — one AnimatedCard containing several InsightRows with internal
  // dividers, per Magna Carta §12, instead of a full card per item.
  groupSection: { marginBottom: spacing.md },
  groupCard: { padding: spacing.lg, paddingVertical: spacing.xs },
  pulseSection: { marginTop: spacing.lg },
  pulseGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
  pulseTile: {
    flexBasis: '48%',
    flexGrow: 1,
    backgroundColor: colors.surfaceSolid,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.cardBorder,
    borderLeftWidth: 3,
    padding: spacing.md,
  },
  pulseLabelRow: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  pulseLabel: { fontSize: 10, fontWeight: '700', letterSpacing: 0.4 },
  pulseValue: { fontSize: 15, fontWeight: '700', color: colors.textPrimary, marginTop: 4 },
  pulseNote: { fontSize: 12, color: colors.textSecondary, marginTop: 2 },
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
  snapshotRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.sm,
  },
  // Per-instance MetricCard sizing overrides (Dashboard's League Snapshot
  // only) — see the comment at the call site.
  snapshotTileThird: { minWidth: '30%', flexBasis: '30%' },
  snapshotTileHalf: { minWidth: '48%', flexBasis: '48%' },
  card: {
    borderLeftWidth: 4,
    padding: spacing.lg,
    marginBottom: spacing.sm,
  },
  cardHeaderRow: { flexDirection: 'row', alignItems: 'center', marginBottom: spacing.xs },
  cardIcon: { marginRight: spacing.xs },
  cardLabel: { fontSize: 11, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.4 },
  cardHeadline: { fontSize: 16, fontWeight: '700', color: colors.textPrimary, marginBottom: 4 },
  cardReason: { fontSize: 13, color: colors.textSecondary, lineHeight: 18, marginTop: spacing.sm },
  tradeBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    marginLeft: 'auto',
    backgroundColor: colors.backgroundElevated,
    borderRadius: radii.pill,
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
  },
  tradeBadgeText: { fontSize: 9, fontWeight: '700', color: colors.textSecondary, letterSpacing: 0.5 },
  sideBlock: { flexDirection: 'row', marginTop: spacing.sm },
  sideBar: { width: 3, borderRadius: 2, marginRight: spacing.sm },
  sideContent: { flex: 1, gap: spacing.xs },
  sideLabel: {
    fontSize: 10,
    fontWeight: '700',
    color: colors.textTertiary,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  assetRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  assetAvatar: {},
  pickDisc: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: colors.backgroundElevated,
    alignItems: 'center',
    justifyContent: 'center',
  },
  assetTextGroup: { flex: 1 },
  assetName: { fontSize: 13, fontWeight: '600', color: colors.textPrimary },
  assetMeta: { fontSize: 11, color: colors.textSecondary },
  assetMetaRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs, marginTop: 1 },
  valueRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: spacing.md,
    paddingTop: spacing.sm,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.hairline,
  },
  valueLabel: { fontSize: 10, fontWeight: '700', color: colors.textTertiary, letterSpacing: 0.4, flexShrink: 1 },
  // A soft tinted chip around the number, not just colored text — "obvious
  // but not sloppy" per coridian_'s brief, so the value result reads as the
  // one clear headline of the row instead of competing with its own label.
  valueChip: {
    borderRadius: radii.pill,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
  },
  valueNumber: { fontSize: 20, fontWeight: '800' },
  meterRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs, marginTop: spacing.md },
  meterLabel: { fontSize: 9, fontWeight: '700', color: colors.textTertiary, letterSpacing: 0.4 },
  meterSegments: { flexDirection: 'row', gap: 3 },
  meterSegment: { width: 18, height: 5, borderRadius: radii.pill },
  meterValue: { fontSize: 11, fontWeight: '600', color: colors.textSecondary },
  destButton: {
    marginTop: spacing.md,
    borderWidth: 1.5,
    borderColor: colors.accent,
    borderRadius: radii.sm,
    paddingVertical: spacing.sm,
    alignItems: 'center',
  },
  destButtonText: { fontSize: 12, fontWeight: '700', color: colors.accent, letterSpacing: 0.4 },
  emptyCard: {
    alignItems: 'center',
    padding: spacing.xl,
    gap: spacing.sm,
  },
  emptyText: { fontSize: 14, color: colors.textSecondary, textAlign: 'center', lineHeight: 20 },
  notReadyText: { textAlign: 'center', color: colors.textSecondary, lineHeight: 20 },
  error: { color: colors.danger, textAlign: 'center' },
  });
}
