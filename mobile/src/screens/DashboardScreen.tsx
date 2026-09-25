import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { ScrollView, StyleSheet, TouchableOpacity, View, type ViewStyle } from 'react-native';
import AppText from '../components/AppText';
import { useFocusEffect } from '@react-navigation/native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useHeaderHeight } from '@react-navigation/elements';
import { Ionicons } from '@expo/vector-icons';

import AnimatedCard from '../components/AnimatedCard';
import BrandedSpinner from '../components/BrandedSpinner';
import EvaluationLensHeaderButton from '../components/EvaluationLensHeaderButton';
import GmStanceHeaderButton from '../components/GmStanceHeaderButton';
import LeagueSwitcherHeaderButton from '../components/LeagueSwitcherHeaderButton';
import GridBackground from '../components/GridBackground';
import IconCircle from '../components/IconCircle';
import InsightRow from '../components/InsightRow';
import NewBadge from '../components/NewBadge';
import PlayerAvatar from '../components/PlayerAvatar';
import PositionBadge from '../components/PositionBadge';
import {
  api,
  type DashboardEntitlementInfo,
  type DashboardItem,
  type DashboardItemCategory,
  type InjuryImpactPlayer,
  type MatchupResponse,
  type PresentationAsset,
  type RankedPlayer,
  type TeamRanking,
  type TeamSnapshot,
} from '../lib/api';
import MetricCard from '../components/MetricCard';
import PremiumLock from '../components/PremiumLock';
import QuickActionsGrid, { type QuickAction } from '../components/QuickActionsGrid';
import ScreenInfoNote from '../components/ScreenInfoNote';
import SectionHeading from '../components/SectionHeading';
import BrandHeaderBar from '../components/BrandHeaderBar';
import TeamAvatar from '../components/TeamAvatar';
import TrajectoryArcs from '../components/TrajectoryArcs';
import { useOrbClearance } from '../lib/orbLayout';
import { getCachedDashboard, setCachedDashboard } from '../lib/dashboardCache';
import { diffAndRecordSeen } from '../lib/sinceLastCheckIn';
import { useScreenHeaderTitle } from '../lib/useScreenHeaderTitle';
import { useDensity } from '../context/DensityContext';
import { useThemeMode } from '../context/ThemeModeContext';
import { radii, spacing, type ThemeColors } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

type Props = NativeStackScreenProps<RootStackParamList, 'Dashboard'>;
type DashboardNavigation = Props['navigation'];

function categoryMeta(
  colors: ThemeColors,
): Record<DashboardItemCategory, { label: string; icon: React.ComponentProps<typeof Ionicons>['name']; color: string }> {
  return {
    top_priority: { label: 'Top Priority', icon: 'flash', color: colors.accent },
    watch: { label: 'Watch', icon: 'eye-outline', color: colors.danger },
    waiver_opportunity: { label: 'Waiver Opportunity', icon: 'swap-horizontal-outline', color: colors.premium },
    league_movement: { label: 'League Movement', icon: 'trending-up-outline', color: colors.textSecondary },
  };
}

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

const CONFIDENCE_LEVELS: Record<string, number> = { high: 3, medium: 2, low: 1 };

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
      note: contender ? `Power #${contender.power_rank}` : 'No contender read available yet.',
      icon: 'flame',
      color: colors.accent,
    },
    {
      label: 'Biggest Rebuilder',
      value: rebuilder?.team_name ?? 'No clear leader',
      note: rebuilder
        ? `Draft Capital #${rebuilder.draft_capital_rank} · ${rebuilder.strategy_label ?? 'Rebuild'}`
        : 'No rebuild read available yet.',
      icon: 'construct',
      color: colors.premium,
    },
    {
      label: 'Draft Capital Leader',
      value: draftLeader?.team_name ?? 'No clear leader',
      note: draftLeader ? `Draft Capital #${draftLeader.draft_capital_rank}` : 'No draft-capital read available yet.',
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
    position: null,
    team: null,
    age: null,
    status: null,
    injury_status: null,
    tier: null,
    score: null,
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

function hasHealthContext(snapshot: TeamSnapshot | null): boolean {
  if (!snapshot) return false;
  const players = snapshot.top_injury_impact_players ?? [];
  const keyInjuries = snapshot.key_injuries_summary?.trim() ?? '';
  const fallbackSummary = snapshot.top_injury_impact_summary?.trim() ?? '';
  return players.length > 0 || Boolean(keyInjuries) || Boolean(fallbackSummary);
}

export default function DashboardScreen({ route, navigation }: Props) {
  const orbClearance = useOrbClearance();
  const headerHeight = useHeaderHeight();
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const { leagueId, leagueName } = route.params;
  const [items, setItems] = useState<DashboardItem[] | null>(null);
  const [teamSnapshot, setTeamSnapshot] = useState<TeamSnapshot | null>(null);
  const [quiet, setQuiet] = useState(false);
  const [quietReason, setQuietReason] = useState('');
  const [notReadyReason, setNotReadyReason] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [newRecommendationIds, setNewRecommendationIds] = useState<Set<string>>(new Set());
  const [isFirstVisit, setIsFirstVisit] = useState(true);
  const [teamRankings, setTeamRankings] = useState<TeamRanking[] | null>(null);
  const [matchup, setMatchup] = useState<MatchupResponse | null>(null);
  const [entitlement, setEntitlement] = useState<DashboardEntitlementInfo | null>(null);
  const { showExplanations } = useDensity();

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

  useFocusEffect(
    useCallback(() => {
      let cancelled = false;
      (async () => {
        // Perceived-performance floor: paint the last-known-good briefing
        // immediately (if one exists) instead of a blank spinner while the
        // live request — real per-request computation server-side — is
        // still in flight. The fetch below always still runs and replaces
        // this the moment it resolves; this never substitutes for it.
        const cached = await getCachedDashboard(leagueId);
        if (!cancelled && cached && !cached.reason) {
          setItems(cached.items);
          setTeamSnapshot(cached.team_snapshot);
          setEntitlement(cached.entitlement ?? null);
          setQuiet(cached.quiet);
          setQuietReason(cached.quiet_reason ?? '');
          setLoading(false);
        }
        try {
          const result = await api.getLeagueDashboard(leagueId);
          if (cancelled) return;
          if (result.reason) {
            setNotReadyReason(result.reason);
          } else {
            setItems(result.items);
            setTeamSnapshot(result.team_snapshot);
            setEntitlement(result.entitlement ?? null);
            setQuiet(result.quiet);
            setQuietReason(result.quiet_reason ?? '');
            void setCachedDashboard(leagueId, result);
            const { newIds, isFirstVisit: firstVisit } = await diffAndRecordSeen(
              leagueId,
              result.items.map((item) => item.recommendation_id),
            );
            if (!cancelled) {
              setNewRecommendationIds(newIds);
              setIsFirstVisit(firstVisit);
            }
          }
        } catch (err) {
          if (!cancelled) setError(err instanceof Error ? err.message : 'Failed to load your Next Move briefing.');
        } finally {
          if (!cancelled) setLoading(false);
        }
      })();
      // Independent, best-effort — League Pulse is a bonus section, not
      // core to the briefing, so a failure here shouldn't touch loading/
      // error state for the rest of the screen.
      api
        .getLeagueTeamRankings(leagueId)
        .then((result) => {
          if (!cancelled) setTeamRankings(result.teams);
        })
        .catch(() => {});
      // Also best-effort: the matchup card is an entry point, not the
      // briefing itself. A bye week, a league without a current week, or a
      // failed call simply means no card.
      api
        .getLeagueMatchup(leagueId)
        .then((result) => {
          if (!cancelled) setMatchup(result);
        })
        .catch(() => {});
      return () => {
        cancelled = true;
      };
    }, [leagueId]),
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
          <TrajectoryArcs width={120} height={82} />
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
          pushing it under the fold. */}
      {matchup ? (
        <WeeklyMatchupCard
          matchup={matchup}
          leagueId={leagueId}
          leagueName={leagueName}
          navigation={navigation}
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
        <MetricCard label="Record" value={record} style={styles.snapshotTileThird} />
        {snapshot.power_rank != null ? (
          <MetricCard
            label="Power"
            value={`#${snapshot.power_rank}`}
            onPress={goToTeams}
            style={styles.snapshotTileThird}
          />
        ) : null}
        {snapshot.franchise_rank != null ? (
          <MetricCard
            label="Franchise"
            value={`#${snapshot.franchise_rank}`}
            onPress={goToTeams}
            style={styles.snapshotTileThird}
          />
        ) : null}
        <MetricCard
          label="Avg Age"
          value={snapshot.average_age != null ? snapshot.average_age.toFixed(1) : '—'}
          style={styles.snapshotTileHalf}
        />
        <MetricCard
          label="Injuries"
          value={injuredCount != null ? String(injuredCount) : '—'}
          valueColor={injuredCount != null && injuredCount > 0 ? colors.danger : undefined}
          style={styles.snapshotTileHalf}
        />
      </View>
    </View>
  );
}

/**
 * Dashboard entry point for the weekly matchup. Demoted from its old
 * "second card on the screen" position into secondary context — "who am I
 * playing" is useful, but it isn't the answer to "what should I do next,"
 * which the Hero above now owns outright (Magna Carta §33/§4). No longer
 * `glow`'d for the same reason: §15 reserves the restrained glow treatment
 * for the one module that actually dominates the page.
 *
 * Shows the season-value edge, NOT a points projection: the app has no
 * weekly-projection feed (see services/mobile_api_service.py's
 * SEASON_VALUE_BASIS_LABEL), so the number here is a season-long
 * value/opportunity total and the card says so on its face.
 */
function WeeklyMatchupCard({
  matchup,
  leagueId,
  leagueName,
  navigation,
}: {
  matchup: MatchupResponse;
  leagueId: string;
  leagueName: string;
  navigation: DashboardNavigation;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const mine = matchup.my_team;
  const opponent = matchup.opponent;
  const comparison = matchup.comparison;
  if (!mine || !opponent || !comparison) return null;

  const edgeColor =
    comparison.edge === 'you'
      ? colors.successBright
      : comparison.edge === 'opponent'
        ? colors.danger
        : colors.textSecondary;

  return (
    <AnimatedCard
      style={StyleSheet.flatten([styles.card, { borderLeftColor: colors.accent } as ViewStyle])}
      onPress={() => navigation.navigate('Matchup', { leagueId, leagueName })}
    >
      <View style={styles.cardHeaderRow}>
        <Ionicons name="american-football" size={15} color={colors.accent} style={styles.cardIcon} />
        <AppText style={[styles.cardLabel, { color: colors.accent }]}>
          {matchup.week != null ? `WEEK ${matchup.week} MATCHUP` : 'THIS WEEK’S MATCHUP'}
        </AppText>
      </View>
      <AppText style={styles.cardHeadline}>vs {opponent.team_name}</AppText>

      <View style={styles.matchupValueRow}>
        <View style={styles.matchupValueSide}>
          <TeamAvatar
            avatarId={mine.avatar_url}
            size={40}
            style={StyleSheet.flatten([styles.matchupAvatar, { borderColor: colors.accent }])}
          />
          <AppText style={styles.matchupSideLabel}>YOU</AppText>
          <AppText style={styles.matchupSideValue}>{Math.round(comparison.my_season_value).toLocaleString()}</AppText>
        </View>
        <AppText style={styles.matchupVersus}>VS</AppText>
        <View style={[styles.matchupValueSide, styles.matchupValueSideRight]}>
          <TeamAvatar
            avatarId={opponent.avatar_url}
            size={40}
            style={StyleSheet.flatten([styles.matchupAvatar, { borderColor: colors.danger }])}
          />
          <AppText style={styles.matchupSideLabel}>THEM</AppText>
          <AppText style={styles.matchupSideValue}>{Math.round(comparison.opponent_season_value).toLocaleString()}</AppText>
        </View>
      </View>

      <AppText style={[styles.matchupEdge, { color: edgeColor }]}>
        {comparison.headline}
        {comparison.edge === 'even'
          ? ''
          : ` (${comparison.margin > 0 ? '+' : ''}${Math.round(comparison.margin).toLocaleString()})`}
      </AppText>
      {/* Straight from the API, never paraphrased into something stronger. */}
      <AppText style={styles.matchupBasis}>{comparison.basis_label}</AppText>

      <View style={styles.destButton}>
        <AppText style={styles.destButtonText}>SEE SUGGESTED STARTERS</AppText>
      </View>
    </AnimatedCard>
  );
}

/** One line of the "what's driving the flag" list — mirrors the engine's own
 * top_injury_impact_summary wording (name (POS, TEAM) - status, impact N,
 * freshness) that web renders, trimmed for a phone-width row. */
function injuryImpactLine(player: InjuryImpactPlayer): string {
  const where = [player.position, player.team].filter(Boolean).join(', ');
  const status = player.injury_status || player.injury_level;
  const detail = [
    status,
    player.roster_relevance,
    player.impact_contribution != null ? `impact ${player.impact_contribution}` : '',
    // Only surface freshness when it undercuts the read — "current"/"recent"
    // updates need no caveat, the same way web only notes stale/unknown ones.
    ['stale', 'aging', 'update unknown'].includes(player.freshness_label) ? player.freshness_label : '',
  ]
    .filter(Boolean)
    .join(' · ');
  const who = where ? `${player.name} (${where})` : player.name;
  return detail ? `${who} — ${detail}` : who;
}

/** The "why" behind an injury-driven Watch flag: which injuries, and which
 * players are actually carrying the impact. Same already-computed fields
 * web shows as its "Key injuries:" caption plus the injury impact note —
 * rendered in the bulleted label/items style TeamRosterScreen already uses
 * for archetype strengths and risks.
 *
 * Folded into the Needs Attention grouped surface (as its own leading
 * block, not a separate bordered card) rather than standing alone the way
 * it used to — same "urgent risk" tier as the Watch rows next to it, so it
 * no longer competes with them for identical visual weight (Magna Carta
 * §12: one grouped surface with internal dividers, not card-per-item).
 * Caller (`NeedsAttentionSection`) already checks `hasHealthContext` before
 * rendering this. */
function TeamHealthContextBlock({ snapshot, last }: { snapshot: TeamSnapshot; last: boolean }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const players = snapshot.top_injury_impact_players ?? [];
  const keyInjuries = snapshot.key_injuries_summary?.trim() ?? '';
  const fallbackSummary = snapshot.top_injury_impact_summary?.trim() ?? '';

  return (
    <View style={[styles.healthBlock, !last && styles.groupDivider]}>
      <View style={styles.cardHeaderRow}>
        <Ionicons name="pulse-outline" size={15} color={colors.danger} style={styles.cardIcon} />
        <AppText style={[styles.cardLabel, { color: colors.danger }]} numberOfLines={1}>
          {(snapshot.health_flag || 'Health context').toUpperCase()}
        </AppText>
      </View>
      {keyInjuries ? <AppText style={styles.healthSummary}>Key injuries: {keyInjuries}</AppText> : null}
      {players.length > 0 ? (
        <View style={styles.detailListGroup}>
          <AppText style={styles.detailListLabel}>Driving the flag</AppText>
          {players.map((player, index) => (
            <AppText key={`${player.player_id || player.name}-${index}`} style={styles.detailListItem}>
              {'•'} {injuryImpactLine(player)}
            </AppText>
          ))}
        </View>
      ) : fallbackSummary ? (
        <AppText style={styles.detailListItem}>{fallbackSummary}</AppText>
      ) : null}
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
          {showHealth ? <TeamHealthContextBlock snapshot={snapshot!} last={rowItems.length === 0} /> : null}
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
  groupDivider: { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.hairline },
  healthBlock: { paddingVertical: spacing.md, gap: spacing.sm },
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
  matchupValueRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginTop: spacing.md,
  },
  matchupValueSide: { flex: 1 },
  matchupValueSideRight: { alignItems: 'flex-end' },
  matchupAvatar: { borderWidth: 2, marginBottom: spacing.xs },
  matchupSideLabel: { fontSize: 10, fontWeight: '800', letterSpacing: 0.6, color: colors.textTertiary },
  matchupSideValue: { fontSize: 20, fontWeight: '800', color: colors.textPrimary, marginTop: 2 },
  matchupVersus: {
    fontSize: 11,
    fontWeight: '800',
    letterSpacing: 0.8,
    color: colors.textTertiary,
    paddingHorizontal: spacing.sm,
  },
  matchupEdge: { fontSize: 13, fontWeight: '700', marginTop: spacing.md },
  matchupBasis: { fontSize: 11, color: colors.textTertiary, lineHeight: 16, marginTop: spacing.xs },
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
  healthSummary: { fontSize: 13, color: colors.textSecondary, lineHeight: 18 },
  // Matches TeamRosterScreen's archetype strengths/risks list styling.
  detailListGroup: { gap: 2 },
  detailListLabel: {
    fontSize: 11,
    fontWeight: '700',
    color: colors.textTertiary,
    textTransform: 'uppercase',
    letterSpacing: 0.4,
    marginBottom: 2,
  },
  detailListItem: { fontSize: 13, color: colors.textSecondary, lineHeight: 18 },
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
