import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { FlatList, StyleSheet, TouchableOpacity, View } from 'react-native';
import AppText from '../components/AppText';
import ToneBadge from '../components/ToneBadge';
import BrandHeaderBar from '../components/BrandHeaderBar';
import { useFocusEffect } from '@react-navigation/native';
import type { NativeStackNavigationProp, NativeStackScreenProps } from '@react-navigation/native-stack';
import { useHeaderHeight } from '@react-navigation/elements';
import { Ionicons } from '@expo/vector-icons';
import { useIsRestoring, useQuery, useQueryClient } from '@tanstack/react-query';

import AccentCard from '../components/AccentCard';
import BrandedSpinner from '../components/BrandedSpinner';
import CircularProgressRing from '../components/CircularProgressRing';
import EvaluationLensHeaderButton from '../components/EvaluationLensHeaderButton';
import GmStanceHeaderButton from '../components/GmStanceHeaderButton';
import LeagueSwitcherHeaderButton from '../components/LeagueSwitcherHeaderButton';
import GridBackground from '../components/GridBackground';
import ManagerProfileModal from '../components/ManagerProfileModal';
import ScreenInfoNote from '../components/ScreenInfoNote';
import SegmentedTabBar from '../components/SegmentedTabBar';
import TeamAvatar from '../components/TeamAvatar';
import PlayoffOddsPanel from './PlayoffOddsPanel';
import NextSteps from '../components/NextSteps';
import ValuesCredit from '../components/ValuesCredit';
import { api, type TeamRanking } from '../lib/api';
import { toUserErrorMessage } from '../lib/errorMessages';
import { isEspnLeagueId } from '../lib/leaguePlatform';
import { useOrbClearance } from '../lib/orbLayout';
import { formatRank, percentileColor, percentileFromRank } from '../lib/percentile';
import { queryKeys } from '../lib/queryKeys';
import { useScreenHeaderTitle } from '../lib/useScreenHeaderTitle';
import { useThemeMode } from '../context/ThemeModeContext';
import { radii, spacing, type ThemeColors } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

type Props = NativeStackScreenProps<RootStackParamList, 'Teams'>;
type TeamsNavigation = NativeStackNavigationProp<RootStackParamList>;

type RankingMetric = NonNullable<Props['route']['params']['metric']>;
type TeamsTab = 'rankings' | 'playoff';

const TEAMS_TABS: Array<{ key: TeamsTab; label: string }> = [
  { key: 'rankings', label: 'Rankings' },
  { key: 'playoff', label: 'Playoff Odds' },
];

/**
 * Per-metric leaderboard config — the one thing that changes between "Teams"
 * (Roster Power, the long-standing default) and a metric-specific drill-down
 * (e.g. Age, opened from My Team's Analysis tab tiles via TeamAnalysisPanel).
 * Every metric here already exists on `TeamRanking` for every team in the
 * league (modules/team_eval.py + modules/league_rankings.py via
 * getLeagueTeamRankings) — nothing computed client-side.
 */
const METRIC_CONFIG: Record<
  RankingMetric,
  {
    title: string;
    pillLabel: string;
    infoLabel: string;
    infoText: string;
    rank: (team: TeamRanking) => number | null;
    tied: (team: TeamRanking) => boolean;
    /** Optional secondary value shown under the rank pill — only Age has
     * a real-unit figure (average roster age) worth surfacing. */
    detail?: (team: TeamRanking) => string | null;
  }
> = {
  power: {
    title: 'League Rankings',
    pillLabel: 'ROSTER POWER',
    infoLabel: 'How Roster Power works',
    infoText:
      'Teams are ordered by Roster Power — roster strength (starters + bench), not record — so you can see exactly where every team in the league stacks up. Your team is marked You and highlighted below.',
    rank: (team) => team.power_rank,
    tied: (team) => team.power_rank_tied,
  },
  franchise: {
    title: 'Franchise Rankings',
    pillLabel: 'FRANCHISE',
    infoLabel: 'How Franchise Rank works',
    infoText:
      'Teams are ordered by Franchise Rank — long-term roster value (youth, talent, draft capital), not just this season’s record. Your team is marked You and highlighted below.',
    rank: (team) => team.franchise_rank,
    tied: (team) => team.franchise_rank_tied,
  },
  draft_capital: {
    title: 'Draft Capital Rankings',
    pillLabel: 'DRAFT',
    infoLabel: 'How Draft Capital Rank works',
    infoText:
      'Teams are ordered by Draft Capital Rank — the value of upcoming draft picks each team holds. Your team is marked You and highlighted below.',
    rank: (team) => team.draft_capital_rank,
    tied: (team) => team.draft_capital_rank_tied,
  },
  starter: {
    title: 'Starter Rankings',
    pillLabel: 'STARTERS',
    infoLabel: 'How Starter Rank works',
    infoText:
      'Teams are ordered by Starter Rank — the combined strength of each team’s starting lineup. Your team is marked You and highlighted below.',
    rank: (team) => team.starter_rank,
    tied: (team) => team.starter_rank_tied,
  },
  bench: {
    title: 'Bench Rankings',
    pillLabel: 'BENCH',
    infoLabel: 'How Bench Rank works',
    infoText:
      'Teams are ordered by Bench Rank — the depth and value of each team’s bench. Your team is marked You and highlighted below.',
    rank: (team) => team.bench_rank,
    tied: (team) => team.bench_rank_tied,
  },
  age: {
    title: 'Age Rankings',
    pillLabel: 'AGE',
    infoLabel: 'How Age Rank works',
    infoText:
      'Teams are ordered by Age Rank — average age of starters, youngest roster ranked #1 — so you can see exactly how your team’s timeline compares across the league. Your team is marked You and highlighted below.',
    rank: (team) => team.age_rank,
    tied: (team) => team.age_rank_tied,
    detail: (team) => (team.average_age != null ? `${team.average_age.toFixed(1)} yrs avg` : null),
  },
};

/**
 * In-screen metric switcher tabs — short pill labels for the same six
 * `METRIC_CONFIG` keys above, in the same order. This screen already fully
 * supported all six (it reads `metric` once from `route.params`), but with
 * no in-screen control to change it, every user landed on and stayed on
 * Power unless a caller happened to deep-link with a specific metric (only
 * the Age tile did). Reuses `SegmentedTabBar` — the same shared
 * pill-switcher Player Detail's Stats/Trends/Schedule/Career/Model tabs and
 * My Team's Overview/Bench/Analysis tabs already use — rather than a
 * page-local control.
 */
const METRIC_TABS: Array<{ key: RankingMetric; label: string }> = [
  { key: 'power', label: 'Power' },
  { key: 'franchise', label: 'Franchise' },
  { key: 'draft_capital', label: 'Draft' },
  { key: 'starter', label: 'Starters' },
  { key: 'bench', label: 'Bench' },
  { key: 'age', label: 'Age' },
];

interface TeamRow {
  rosterId: number | string;
  teamName: string;
  ownerName: string;
  avatarId: string;
  playerIds: string[];
  isMine: boolean;
  metricRank: number | null;
  metricRankTied: boolean;
  metricDetail: string | null;
  recordLabel: string | null;
  archetypeLabel: string | null;
  tradeTendency: string | null;
  /** Zero, one, or several real, data-backed team signals (see
   * TEAM_BADGE_VISUALS) — a team can plausibly earn more than one at once
   * (e.g. both "Highly Active" and "Pick Hoarder"), so this always renders
   * as a wrapping row rather than a single slot. */
  signalBadges: string[];
}

/** Visual treatment for every real, data-backed team signal shown on a
 * Teams row — same icon-plus-colored-text pattern the "Real history of
 * buying/selling" trade-tendency badge already uses (TeamRowCard below),
 * reused rather than inventing a new chip/box treatment. Tone picks the
 * semantic color token that actually matches each signal's meaning
 * (mobile/UI_COLOR_SYSTEM_AUDIT.md: one consistent meaning per color
 * family) — most of these are neutral play-style descriptors (textSecondary),
 * while the two with a real positive/negative read (an active streak, a
 * roster-concentration risk) get success/danger. */
const TEAM_BADGE_VISUALS: Record<string, { icon: keyof typeof Ionicons.glyphMap; tone: 'neutral' | 'positive' | 'negative' }> = {
  'Highly Active': { icon: 'flash', tone: 'neutral' },
  'Quiet Manager': { icon: 'pause', tone: 'neutral' },
  'Pick Hoarder': { icon: 'layers', tone: 'neutral' },
  'Pick Seller': { icon: 'swap-horizontal', tone: 'neutral' },
  'Veteran Collector': { icon: 'time', tone: 'neutral' },
  'Youth Builder': { icon: 'leaf', tone: 'neutral' },
  'Hot Streak': { icon: 'flame', tone: 'positive' },
  'Cold Streak': { icon: 'snow', tone: 'negative' },
  'Top-Heavy Roster': { icon: 'alert-circle', tone: 'negative' },
};

function toneColor(tone: 'neutral' | 'positive' | 'negative', colors: ThemeColors): string {
  if (tone === 'positive') return colors.success;
  if (tone === 'negative') return colors.danger;
  return colors.textSecondary;
}

/** Metric-independent roster data — fetched once per league focus, not
 * refetched on every in-screen metric switch. The in-screen switcher below
 * only needs to re-derive rank/detail/sort per `TeamRanking` already held
 * here (see the `teams` memo), not re-hit the network. */
interface BaseTeamRow {
  rosterId: number | string;
  teamName: string;
  ownerName: string;
  avatarId: string;
  playerIds: string[];
  isMine: boolean;
  ranking: TeamRanking | undefined;
}

/**
 * League Rankings host: one screen with a top tab switcher (same pattern as
 * the Trades host) holding the Rankings leaderboard and Playoff Odds. Each
 * tab body is its own component, lazy-mounted on first visit and then kept
 * mounted so switching back doesn't re-fetch. Playoff Odds stays Pro-gated
 * exactly as before: its panel makes the same request and renders the same
 * PremiumLock when the backend says the viewer isn't premium. The retired
 * 'PlayoffOdds' route redirects here with `initialTab: 'playoff'`.
 */
export default function TeamsScreen({ route, navigation }: Props) {
  const { leagueId, leagueName, metric, initialTab } = route.params;
  const headerHeight = useHeaderHeight();
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  // Playoff Odds was never available for ESPN leagues (the old route sat
  // behind the ESPN gate), so ESPN only gets the Rankings tab.
  const espn = isEspnLeagueId(leagueId);
  const tabOptions = espn ? TEAMS_TABS.filter((option) => option.key === 'rankings') : TEAMS_TABS;
  const firstTab: TeamsTab = espn ? 'rankings' : (initialTab ?? 'rankings');
  const [activeTab, setActiveTab] = useState<TeamsTab>(firstTab);
  const [visitedTabs, setVisitedTabs] = useState<Set<TeamsTab>>(() => new Set<TeamsTab>([firstTab]));
  const onChangeTab = useCallback((tab: TeamsTab) => {
    setActiveTab(tab);
    setVisitedTabs((prev) => (prev.has(tab) ? prev : new Set(prev).add(tab)));
  }, []);
  // Picked from the GM orb while League Rankings is already open.
  useEffect(() => {
    if (initialTab && !espn) onChangeTab(initialTab);
  }, [initialTab, espn, onChangeTab]);

  return (
    <View style={styles.root}>
      <GridBackground />
      <View style={[styles.topSection, { paddingTop: headerHeight }]}>
        <BrandHeaderBar leagueId={leagueId} leagueName={leagueName} />
        {tabOptions.length > 1 ? (
          <View style={styles.tabBarWrap}>
            <SegmentedTabBar<TeamsTab> options={tabOptions} active={activeTab} onChange={onChangeTab} />
          </View>
        ) : null}
      </View>
      <View style={styles.contentArea}>
        {visitedTabs.has('rankings') ? (
          <View style={[styles.tabPane, activeTab !== 'rankings' && styles.tabPaneHidden]}>
            <RankingsPanel
              leagueId={leagueId}
              leagueName={leagueName}
              initialMetric={metric}
              active={activeTab === 'rankings'}
              navigation={navigation}
            />
          </View>
        ) : null}
        {visitedTabs.has('playoff') ? (
          <View style={[styles.tabPane, activeTab !== 'playoff' && styles.tabPaneHidden]}>
            <PlayoffOddsPanel leagueId={leagueId} leagueName={leagueName} />
          </View>
        ) : null}
      </View>
    </View>
  );
}

function RankingsPanel({
  leagueId,
  leagueName,
  initialMetric,
  active,
  navigation,
}: {
  leagueId: string;
  leagueName: string;
  initialMetric?: RankingMetric;
  active: boolean;
  navigation: TeamsNavigation;
}) {
  const orbClearance = useOrbClearance();
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  // Local state, seeded once from `route.params.metric` (e.g. the Age tile's
  // deep link) rather than read directly from route.params on every render —
  // the in-screen switcher below changes this same state afterward, and a
  // user can land on any of the six metrics in-screen regardless of how they
  // navigated in.
  const [metric, setMetric] = useState<RankingMetric>(initialMetric ?? 'power');
  const config = METRIC_CONFIG[metric];
  const queryClient = useQueryClient();
  const [profileTeam, setProfileTeam] = useState<{ rosterId: number | string; teamName: string; ownerName: string; avatarId: string } | null>(null);
  // Gates every query below until the persisted AsyncStorage cache has
  // finished hydrating back into the in-memory QueryClient — same guard
  // Dashboard/Matchup use, so a query here never fires before last session's
  // cached response is restored.
  const isRestoring = useIsRestoring();

  const teamProfilesQuery = useQuery({
    queryKey: queryKeys.teamProfiles(leagueId),
    queryFn: () => api.getLeagueTeamProfiles(leagueId),
    enabled: !isRestoring,
  });
  const rostersQuery = useQuery({
    queryKey: queryKeys.leagueRosters(leagueId),
    queryFn: () => api.getLeagueRosters(leagueId),
    enabled: !isRestoring,
  });
  const myRosterQuery = useQuery({
    queryKey: queryKeys.myRoster(leagueId),
    queryFn: () => api.getMyRoster(leagueId),
    enabled: !isRestoring,
  });
  // Same endpoint Dashboard's League Pulse section and MyTeamScreen's Team
  // Snapshot both fetch — shares one cache entry under
  // queryKeys.teamRankings(leagueId) instead of each screen hitting it
  // independently.
  const teamRankingsQuery = useQuery({
    queryKey: queryKeys.teamRankings(leagueId),
    queryFn: () => api.getLeagueTeamRankings(leagueId),
    enabled: !isRestoring,
  });

  // Header title follows the active tab: the metric-specific rankings title,
  // or Playoff Odds while that tab is showing.
  useScreenHeaderTitle(navigation, active ? config.title : 'Playoff Odds', leagueName);

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
      void queryClient.invalidateQueries({ queryKey: queryKeys.teamProfiles(leagueId) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.leagueRosters(leagueId) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.myRoster(leagueId) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.teamRankings(leagueId) });
    }, [queryClient, leagueId]),
  );

  // Metric-independent roster data, derived from the four queries above —
  // the in-screen metric switcher re-derives per-metric rank/sort from this
  // below instead of refetching, so switching metrics stays instant/in-place.
  // `myRosterQuery`/`teamRankingsQuery` are best-effort enrichment (the "You"
  // badge and rank pills, not core to rendering a row at all), so a failure
  // on either just falls back to an empty/undefined read here rather than
  // blocking the whole screen — same soft-fail the old Promise.all
  // `.catch()` fallbacks gave them.
  const baseRows: BaseTeamRow[] = useMemo(() => {
    const profiles = teamProfilesQuery.data?.profiles;
    const rosters = rostersQuery.data?.rosters;
    if (!profiles || !rosters) return [];
    const myRosterId = myRosterQuery.data?.roster
      ? String(myRosterQuery.data.roster.roster_id ?? '')
      : '';
    const rankingsByRoster = new Map(
      (teamRankingsQuery.data?.teams ?? []).map((team) => [team.roster_id, team]),
    );
    return rosters.map((roster) => {
      const rosterId = String(roster.roster_id ?? '');
      const players = Array.isArray(roster.players) ? roster.players : [];
      const profile = profiles[rosterId];
      return {
        rosterId,
        teamName: profile?.team_name || 'Unclaimed team',
        ownerName: profile?.owner_name || '',
        avatarId: profile?.avatar_id || '',
        playerIds: players.map(String),
        isMine: Boolean(myRosterId) && rosterId === myRosterId,
        ranking: rankingsByRoster.get(rosterId),
      };
    });
  }, [teamProfilesQuery.data, rostersQuery.data, myRosterQuery.data, teamRankingsQuery.data]);

  // Only teamProfiles/rosters are core to rendering any row at all — myRoster
  // ("You" badge) and teamRankings (rank pills) are best-effort enrichment
  // that can paint in slightly afterward without blocking the initial list.
  const loading = isRestoring || teamProfilesQuery.isPending || rostersQuery.isPending;
  const error =
    (teamProfilesQuery.isError && !teamProfilesQuery.data) || (rostersQuery.isError && !rostersQuery.data)
      ? toUserErrorMessage(teamProfilesQuery.error ?? rostersQuery.error, 'Failed to load teams.')
      : null;

  // Per-metric rank/detail + sort, derived from the metric-independent fetch
  // above — switching `metric` here never re-hits the network.
  const teams: TeamRow[] = useMemo(() => {
    const rows = baseRows.map((row) => {
      const { ranking } = row;
      return {
        rosterId: row.rosterId,
        teamName: row.teamName,
        ownerName: row.ownerName,
        avatarId: row.avatarId,
        playerIds: row.playerIds,
        isMine: row.isMine,
        metricRank: ranking ? config.rank(ranking) : null,
        metricRankTied: ranking ? config.tied(ranking) : false,
        metricDetail: ranking && config.detail ? config.detail(ranking) : null,
        recordLabel: ranking?.record_label ?? null,
        archetypeLabel: ranking?.archetype_label ?? null,
        tradeTendency: ranking?.trade_tendency && ranking.trade_tendency !== 'Neutral' ? ranking.trade_tendency : null,
        signalBadges: ranking?.team_badges ?? [],
      };
    });
    // Pure metric-rank order — no longer pins the caller's own team first,
    // since that made a rank-4 team appear above rank-1 with no explanation.
    // The "You" badge + left-accent row below is how a user finds their own
    // row now instead of it always being #1 in the list regardless of rank.
    rows.sort((a, b) => {
      if (a.metricRank == null && b.metricRank == null) return 0;
      if (a.metricRank == null) return 1;
      if (b.metricRank == null) return -1;
      return a.metricRank - b.metricRank;
    });
    return rows;
  }, [baseRows, config]);

  // Percentile denominator is the count of teams the backend actually ranked
  // for this metric (not every roster — an unclaimed team has no rank and
  // shouldn't shrink the league size other teams are compared against).
  const myRanking = useMemo(() => baseRows.find((row) => row.isMine)?.ranking, [baseRows]);
  const rankedTeamCount = useMemo(() => teams.filter((team) => team.metricRank != null).length, [teams]);

  if (loading) {
    return <BrandedSpinner style={styles.center} />;
  }

  if (error) {
    return (
      <View style={styles.center}>
        <AppText style={styles.error}>{error}</AppText>
      </View>
    );
  }

  return (
    <View style={styles.root}>
      <GridBackground />
      <View style={styles.metricTabBarWrap}>
        <SegmentedTabBar options={METRIC_TABS} active={metric} onChange={setMetric} />
      </View>
      <FlatList
        ListFooterComponent={
          <>
            <NextSteps title="Make a move" steps={['trade-hub', 'matchup']} leagueId={leagueId} leagueName={leagueName} />
            <ValuesCredit />
          </>
        }
        style={styles.list}
        contentContainerStyle={[styles.listContent, { paddingBottom: orbClearance }]}
        data={teams}
        keyExtractor={(item) => String(item.rosterId)}
        ListHeaderComponent={
          <View style={styles.infoNoteWrap}>
            {myRanking ? <YourStandingCard me={myRanking} total={teamRankingsQuery.data?.teams.length ?? 0} colors={colors} styles={styles} /> : null}
            <ScreenInfoNote label={config.infoLabel} text={config.infoText} />
          </View>
        }
        renderItem={({ item, index }) => (
          <TeamRowCard
            item={item}
            isFirst={index === 0}
            isLast={index === teams.length - 1}
            rankedTeamCount={rankedTeamCount}
            pillLabel={config.pillLabel}
            showTrophy={metric === 'power'}
            colors={colors}
            styles={styles}
            onOpenProfile={() => setProfileTeam({ rosterId: item.rosterId, teamName: item.teamName, ownerName: item.ownerName, avatarId: item.avatarId })}
            onPress={() =>
              navigation.navigate('TeamRoster', {
                ownerName: item.teamName,
                playerIds: item.playerIds,
                leagueId,
                leagueName,
                rosterId: String(item.rosterId),
              })
            }
          />
        )}
      />
      {profileTeam ? (
        <ManagerProfileModal
          visible
          onClose={() => setProfileTeam(null)}
          leagueId={leagueId}
          leagueName={leagueName}
          rosterId={profileTeam.rosterId}
          teamName={profileTeam.teamName}
          ownerName={profileTeam.ownerName}
          avatarId={profileTeam.avatarId}
        />
      ) : null}
    </View>
  );
}

function TeamRowCard({
  item,
  isFirst,
  isLast,
  rankedTeamCount,
  pillLabel,
  showTrophy,
  colors,
  styles,
  onPress,
  onOpenProfile,
}: {
  item: TeamRow;
  isFirst: boolean;
  isLast: boolean;
  rankedTeamCount: number;
  pillLabel: string;
  /** Trophy-for-rank-1 styling only applies to Roster Power — "league
   * champion" is a Roster Power concept, so other metrics (e.g. youngest
   * roster for Age) just get the plain rank pill instead of a misleading
   * trophy. */
  showTrophy: boolean;
  colors: ThemeColors;
  styles: ReturnType<typeof createStyles>;
  onPress: () => void;
  /** Opens the manager profile (Manager Tendencies). */
  onOpenProfile: () => void;
}) {
  const isChampion = showTrophy && item.metricRank === 1;
  const rankPercentile = percentileFromRank(item.metricRank, rankedTeamCount);
  // League #1 keeps the same premium/gold hue as an award badge instead of
  // the percentile ramp — a leaderboard's top spot should read as "the"
  // rank at a glance. Every other rank uses the shared percentile color
  // ramp (§27) so a bottom-of-the-league team reads as weak (red/amber)
  // and a near-top team reads as strong (green), not one flat accent color
  // regardless of where in the pack it actually sits.
  const rankColor = isChampion ? colors.premium : percentileColor(rankPercentile, colors);

  return (
    <TouchableOpacity
      activeOpacity={0.7}
      onPress={onPress}
      style={[
        styles.row,
        isFirst && styles.rowFirst,
        isLast && styles.rowLast,
        !isLast && styles.rowDivider,
        item.isMine && styles.rowMine,
      ]}
    >
      <TeamAvatar avatarId={item.avatarId} size={36} style={styles.avatar} />
      <View style={styles.ownerGroup}>
        <View style={styles.nameRow}>
          <AppText style={styles.owner} numberOfLines={1}>
            {item.teamName}
          </AppText>
          {item.isMine ? (
            <ToneBadge label="You" color={colors.accent} textColor={colors.onAccent} solid />
          ) : null}
        </View>
        {item.recordLabel ? <AppText style={styles.record}>{item.recordLabel}</AppText> : null}
        {item.archetypeLabel ? (
          <View style={styles.archetypeBadge}>
            <AppText style={styles.archetypeBadgeText} numberOfLines={1}>
              {item.archetypeLabel}
            </AppText>
          </View>
        ) : null}
        {item.tradeTendency || item.signalBadges.length > 0 ? (
          <View style={styles.signalBadgeWrap}>
            {item.tradeTendency ? (
              <View style={styles.tendencyRow}>
                <Ionicons
                  name={item.tradeTendency === 'Seller' ? 'trending-down' : 'trending-up'}
                  size={11}
                  color={item.tradeTendency === 'Seller' ? colors.accentSoft : colors.premium}
                />
                <AppText
                  style={[
                    styles.tendencyText,
                    { color: item.tradeTendency === 'Seller' ? colors.accentSoft : colors.premium },
                  ]}
                  numberOfLines={1}
                >
                  Real history of {item.tradeTendency === 'Seller' ? 'selling' : 'buying'}
                </AppText>
              </View>
            ) : null}
            {item.signalBadges.map((label) => {
              const visual = TEAM_BADGE_VISUALS[label];
              if (!visual) return null;
              const color = toneColor(visual.tone, colors);
              return (
                <View key={label} style={styles.tendencyRow}>
                  <Ionicons name={visual.icon} size={11} color={color} />
                  <AppText style={[styles.tendencyText, { color }]} numberOfLines={1}>
                    {label}
                  </AppText>
                </View>
              );
            })}
          </View>
        ) : null}
      </View>
      <TouchableOpacity
        onPress={onOpenProfile}
        hitSlop={8}
        accessibilityRole="button"
        accessibilityLabel={`${item.teamName} manager profile`}
        style={{ paddingHorizontal: spacing.xs }}
      >
        <Ionicons name="information-circle-outline" size={18} color={colors.textSecondary} />
      </TouchableOpacity>
      {item.metricRank != null ? (
        <View style={[styles.rankPill, isChampion && styles.rankPillFirst, { borderColor: `${rankColor}80` }]}>
          {isChampion ? (
            <Ionicons name="trophy" size={13} color={rankColor} style={styles.rankTrophy} />
          ) : (
            <AppText style={styles.rankLabel}>{pillLabel}</AppText>
          )}
          <AppText style={[styles.rankValue, { color: rankColor }]}>{formatRank(item.metricRank, item.metricRankTied)}</AppText>
          {item.metricDetail ? (
            <AppText style={styles.rankDetail} numberOfLines={1}>
              {item.metricDetail}
            </AppText>
          ) : null}
        </View>
      ) : (
        <View style={styles.countPill}>
          <AppText style={styles.count}>{item.playerIds.length}</AppText>
        </View>
      )}
    </TouchableOpacity>
  );
}

/** "Your standing" hero above the board: Roster Power percentile ring, record, and the other four ranks as mini bars (mirrors web-next's YourStandingCard). */
function YourStandingCard({
  me,
  total,
  colors,
  styles,
}: {
  me: TeamRanking;
  total: number;
  colors: ThemeColors;
  styles: ReturnType<typeof createStyles>;
}) {
  const powerPercent = percentileFromRank(me.power_rank, total);
  const minis: Array<{ label: string; rank: number | null; tied: boolean }> = [
    { label: 'Franchise', rank: me.franchise_rank, tied: me.franchise_rank_tied },
    { label: 'Draft Capital', rank: me.draft_capital_rank, tied: me.draft_capital_rank_tied },
    { label: 'Starters', rank: me.starter_rank, tied: me.starter_rank_tied },
    { label: 'Bench', rank: me.bench_rank, tied: me.bench_rank_tied },
  ];
  return (
    <AccentCard accent={colors.accent} style={styles.standingCard}>
      <View style={styles.standingHead}>
        <CircularProgressRing
          percent={powerPercent ?? 0}
          size={56}
          strokeWidth={6}
          color={percentileColor(powerPercent, colors)}
          valueLabel={powerPercent === null ? '—' : `${powerPercent}`}
          valueFontScale={0.32}
        />
        <View style={styles.standingHeadText}>
          <AppText style={styles.standingEyebrow}>Your standing</AppText>
          <AppText style={styles.standingTitle}>
            Roster Power {formatRank(me.power_rank, me.power_rank_tied)}{total ? ` of ${total}` : ''}
          </AppText>
          <AppText style={styles.standingMeta}>{me.record_label ? `Record ${me.record_label}` : 'Record not available'}</AppText>
        </View>
      </View>
      <View style={styles.standingGrid}>
        {minis.map(({ label, rank, tied }) => {
          const percentile = percentileFromRank(rank, total);
          const tone = percentileColor(percentile, colors);
          return (
            <View key={label} style={styles.standingMini}>
              <View style={styles.standingMiniHead}>
                <AppText style={styles.standingMiniLabel}>{label}</AppText>
                <AppText style={[styles.standingMiniRank, { color: tone }]}>{formatRank(rank, tied)}</AppText>
              </View>
              <View style={styles.standingTrack}>
                <View style={[styles.standingFill, { width: `${percentile ?? 0}%`, backgroundColor: tone }]} />
              </View>
            </View>
          );
        })}
      </View>
    </AccentCard>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
  headerButtonRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  root: { flex: 1, backgroundColor: 'transparent' },
  topSection: { backgroundColor: 'transparent' },
  tabBarWrap: { paddingHorizontal: spacing.lg, paddingTop: spacing.xs, paddingBottom: spacing.sm },
  contentArea: { flex: 1 },
  tabPane: { flex: 1 },
  // display: 'none' (not unmounting) keeps each tab's state alive across switches.
  tabPaneHidden: { display: 'none' },
  list: { backgroundColor: 'transparent' },
  listContent: { padding: spacing.lg },
  metricTabBarWrap: { paddingHorizontal: spacing.lg, paddingTop: spacing.sm },
  infoNoteWrap: { marginBottom: spacing.md, gap: spacing.md },
  standingCard: { gap: spacing.md },
  standingHead: { flexDirection: 'row', alignItems: 'center', gap: spacing.md },
  standingHeadText: { flex: 1, minWidth: 0 },
  standingEyebrow: { fontSize: 11, fontWeight: '800', color: colors.accent, textTransform: 'uppercase', letterSpacing: 0.85 },
  standingTitle: { fontSize: 16, fontWeight: '800', color: colors.textPrimary },
  standingMeta: { fontSize: 12, color: colors.textTertiary },
  standingGrid: { flexDirection: 'row', flexWrap: 'wrap', columnGap: spacing.lg, rowGap: spacing.sm },
  standingMini: { width: '47%', flexGrow: 1, gap: 4 },
  standingMiniHead: { flexDirection: 'row', alignItems: 'baseline', justifyContent: 'space-between', gap: spacing.sm },
  standingMiniLabel: { fontSize: 12, color: colors.textTertiary },
  standingMiniRank: { fontSize: 12, fontWeight: '800' },
  standingTrack: { height: 6, width: '100%', backgroundColor: colors.border, borderRadius: 3, overflow: 'hidden' },
  standingFill: { height: '100%' },
  center: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: spacing.xl,
    backgroundColor: colors.background,
  },
  // Continuous grouped surface with internal dividers (Magna Carta §12)
  // instead of a separately-bordered, separately-shadowed card per team —
  // every team is a peer row in one leaderboard, not N independent modules.
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.glass,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
    borderLeftWidth: StyleSheet.hairlineWidth * 1.5,
    borderRightWidth: StyleSheet.hairlineWidth * 1.5,
    borderColor: colors.glassBorder,
  },
  rowFirst: { borderTopWidth: StyleSheet.hairlineWidth * 1.5, borderTopLeftRadius: radii.md, borderTopRightRadius: radii.md },
  rowLast: { borderBottomWidth: StyleSheet.hairlineWidth * 1.5, borderBottomLeftRadius: radii.md, borderBottomRightRadius: radii.md },
  rowDivider: { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border },
  // The user's own row gets a cyan left rail + faint tint — the same
  // badge-tint token used elsewhere for cyan emphasis (§14: cyan reserved
  // for selection/important-module cues), not a page-specific color.
  rowMine: {
    borderLeftWidth: 3,
    borderLeftColor: colors.accent,
    backgroundColor: colors.badgeBackground,
  },
  avatar: { marginRight: spacing.sm },
  ownerGroup: { flex: 1, marginRight: spacing.sm },
  nameRow: { flexDirection: 'row', alignItems: 'center' },
  owner: { fontSize: 16, fontWeight: '500', color: colors.textPrimary, marginRight: spacing.sm, flexShrink: 1 },
  record: { fontSize: 12, color: colors.textSecondary, marginTop: 2 },
  archetypeBadge: {
    alignSelf: 'flex-start',
    backgroundColor: colors.badgeBackground,
    borderRadius: radii.pill,
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
    marginTop: spacing.xs,
  },
  archetypeBadgeText: { fontSize: 10, fontWeight: '700', color: colors.badgeText },
  // Wraps every real-signal row (trade tendency + team_badges) so a team
  // with several badges at once (e.g. "Highly Active" + "Pick Hoarder")
  // flows them onto a second line instead of clipping or overlapping.
  signalBadgeWrap: { flexDirection: 'row', flexWrap: 'wrap', columnGap: spacing.sm, rowGap: 2, marginTop: 3 },
  tendencyRow: { flexDirection: 'row', alignItems: 'center', gap: 3 },
  tendencyText: { fontSize: 11, fontWeight: '600' },
  rankPill: {
    backgroundColor: colors.background,
    borderRadius: radii.sm,
    borderWidth: 1,
    paddingHorizontal: spacing.sm,
    paddingVertical: 4,
    alignItems: 'center',
    minWidth: 52,
  },
  rankLabel: {
    fontSize: 9,
    fontWeight: '700',
    color: colors.textTertiary,
    letterSpacing: 0.4,
  },
  rankValue: { fontSize: 15, fontWeight: '700' },
  rankDetail: { fontSize: 9, fontWeight: '600', color: colors.textTertiary, marginTop: 1 },
  // League #1 gets the same premium/gold hue as an award badge instead of
  // the standard accent — a leaderboard's top spot should read as "the"
  // rank at a glance, not just another pill in the same color scheme as
  // the rest of the pack.
  rankPillFirst: { backgroundColor: `${colors.premium}1F` },
  rankTrophy: { marginBottom: 1 },
  countPill: {
    backgroundColor: colors.background,
    borderRadius: radii.pill,
    paddingHorizontal: spacing.sm,
    paddingVertical: 3,
    minWidth: 28,
    alignItems: 'center',
  },
  count: { fontSize: 13, fontWeight: '600', color: colors.textSecondary },
  error: { color: colors.danger, textAlign: 'center' },
  });
}
