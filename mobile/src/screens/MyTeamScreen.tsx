import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { ScrollView, StyleSheet, TouchableOpacity, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import AppText from '../components/AppText';
import SectionHeading from '../components/SectionHeading';
import { useFocusEffect } from '@react-navigation/native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useHeaderHeight } from '@react-navigation/elements';
import { useIsRestoring, useQuery, useQueryClient } from '@tanstack/react-query';

import AnimatedCard from '../components/AnimatedCard';
import EmptyState from '../components/EmptyState';
import ErrorState from '../components/ErrorState';
import EvaluationLensHeaderButton from '../components/EvaluationLensHeaderButton';
import GmStanceHeaderButton from '../components/GmStanceHeaderButton';
import LeagueSwitcherHeaderButton from '../components/LeagueSwitcherHeaderButton';
import BrandHeaderBar from '../components/BrandHeaderBar';
import CircularProgressRing from '../components/CircularProgressRing';
import GridBackground from '../components/GridBackground';
import DashboardStatRow from '../components/DashboardStatRow';
import PositionBadge from '../components/PositionBadge';
import PlayerIdentityRow from '../components/PlayerIdentityRow';
import { SkeletonCard, SkeletonRows } from '../components/SkeletonBlock';
import SegmentedTabBar from '../components/SegmentedTabBar';
import TeamAnalysisPanel, { hasRosterAnalysis } from '../components/TeamAnalysisPanel';
import ToneBadge from '../components/ToneBadge';
import { waiverInjuryDisplay } from '../components/WaiverRecommendationCard';
import ValuesCredit from '../components/ValuesCredit';
import { api, type KeeperPlayerInfo, type KeepersResponse, type LineupPlayer, type TeamRanking } from '../lib/api';
import { buildRosterComposition, buildTeamAnalysisRows, type CompositionSegment, type TeamAnalysisRow } from '../lib/myTeamAnalysis';
import { toUserErrorMessage } from '../lib/errorMessages';
import { isByeOnlyLabel, lineupStatusLabel, openSlotsMessage } from '../lib/lineupAvailability';
import { useOrbClearance } from '../lib/orbLayout';
import { formatRank, percentileColor, percentileFromRank } from '../lib/percentile';
import { queryKeys } from '../lib/queryKeys';
import { useScreenHeaderTitle } from '../lib/useScreenHeaderTitle';
import { useThemeMode } from '../context/ThemeModeContext';
import { radii, spacing, type ThemeColors } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

type Props = NativeStackScreenProps<RootStackParamList, 'MyTeam'>;

const NO_LEAGUE_REASONS = new Set([
  'no_sleeper_username_linked',
  'sleeper_user_not_found',
  'not_a_member_of_league',
]);

function reasonMessage(reason: string): string | null {
  if (NO_LEAGUE_REASONS.has(reason)) {
    return "Link your Sleeper account and join this league from Home to see your lineup.";
  }
  if (reason === 'empty_roster') {
    return "Your roster in this league looks empty.";
  }
  if (reason === 'no_player_data') {
    return "Player data isn't available right now — try again in a bit.";
  }
  return null;
}

function toRankedPlayer(player: LineupPlayer) {
  return {
    player_id: player.player_id,
    name: player.name,
    position: player.position,
    team: player.team,
    age: player.age,
    status: player.status,
    injury_status: player.injury_status,
    tier: player.tier,
    score: player.score,
    overall_rank: null,
    position_rank: null,
    rank_unavailable_reason: null,
    opportunity_label: player.opportunity_label,
  };
}

type RosterTabKey = 'starters' | 'bench' | 'ir' | 'taxi';

const ANALYSIS_TONE_COLOR = (tone: TeamAnalysisRow['tone'], colors: ThemeColors): string =>
  tone === 'success'
    ? colors.success
    : tone === 'warning'
      ? colors.premium
      : tone === 'danger'
        ? colors.danger
        : colors.accent;

export default function MyTeamScreen({ route, navigation }: Props) {
  const orbClearance = useOrbClearance();
  const headerHeight = useHeaderHeight();
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const { leagueId, leagueName } = route.params;
  const [rosterTab, setRosterTab] = useState<RosterTabKey>('starters');
  const [showFullAnalysis, setShowFullAnalysis] = useState(false);
  const queryClient = useQueryClient();
  // Gates the queries below until the persisted AsyncStorage cache has
  // finished hydrating back into the in-memory QueryClient.
  const isRestoring = useIsRestoring();

  const myTeamQuery = useQuery({
    queryKey: queryKeys.myTeam(leagueId),
    queryFn: () => api.getLeagueMyTeam(leagueId),
    enabled: !isRestoring,
  });
  // Best-effort enrichment (Team Snapshot's rank/archetype); shares the cache
  // entry Dashboard and Teams use.
  const teamRankingsQuery = useQuery({
    queryKey: queryKeys.teamRankings(leagueId),
    queryFn: () => api.getLeagueTeamRankings(leagueId),
    enabled: !isRestoring,
  });
  // Best-effort: per-position room statuses for Team Analysis.
  const needsQuery = useQuery({
    queryKey: queryKeys.myTeamNeeds(leagueId),
    queryFn: () => api.getLeagueMyTeamNeeds(leagueId),
    enabled: !isRestoring,
  });
  // Best-effort: only keeper leagues return tags/candidates.
  const keepersQuery = useQuery({
    queryKey: queryKeys.keepers(leagueId),
    queryFn: () => api.getLeagueKeepers(leagueId),
    enabled: !isRestoring,
  });
  const keepers = keepersQuery.data?.is_keeper_league ? keepersQuery.data : null;

  useScreenHeaderTitle(navigation, 'My Team', leagueName);

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

  // Re-check on regaining focus; cached data stays on screen throughout.
  useFocusEffect(
    useCallback(() => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.myTeam(leagueId) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.teamRankings(leagueId) });
    }, [queryClient, leagueId]),
  );

  const myTeamData = myTeamQuery.data;
  // Best ball: Sleeper sets the lineup itself, so the suggested
  // starters/bench split is one roster list (suggested slot labels stripped).
  const bestBall = myTeamData?.best_ball === true;
  const rawStarters = useMemo<LineupPlayer[]>(() => myTeamData?.starters ?? [], [myTeamData]);
  const rawBench = useMemo<LineupPlayer[]>(() => myTeamData?.bench ?? [], [myTeamData]);
  const isActiveBench = (p: LineupPlayer) => p.roster_slot !== 'ir' && p.roster_slot !== 'taxi';
  const starters: LineupPlayer[] = bestBall
    ? [...rawStarters, ...rawBench.filter(isActiveBench)].map((p) => ({ ...p, slot: 'BENCH' }))
    : rawStarters;
  const activeBench = bestBall ? [] : rawBench.filter(isActiveBench);
  const irBench = rawBench.filter((p) => p.roster_slot === 'ir');
  const taxiBench = rawBench.filter((p) => p.roster_slot === 'taxi');
  const notice = myTeamData?.reason ? reasonMessage(myTeamData.reason) : null;
  const leagueSize = teamRankingsQuery.data?.teams.length ?? 0;
  const myTeam: TeamRanking | null = myTeamData?.roster_id
    ? teamRankingsQuery.data?.teams.find((team) => team.roster_id === myTeamData.roster_id) ?? null
    : null;

  const loading = isRestoring || myTeamQuery.isPending;
  const error =
    myTeamQuery.isError && !myTeamData
      ? toUserErrorMessage(myTeamQuery.error, 'Failed to load your lineup.')
      : null;

  const startersValue = useMemo(() => rawStarters.reduce((sum, p) => sum + (p.score ?? 0), 0), [rawStarters]);
  const teamValue = useMemo(
    () => startersValue + rawBench.reduce((sum, p) => sum + (p.score ?? 0), 0),
    [startersValue, rawBench],
  );

  const analysisRows = useMemo(
    () => (needsQuery.data?.ok ? buildTeamAnalysisRows(needsQuery.data) : []),
    [needsQuery.data],
  );

  const composition = buildRosterComposition(
        bestBall
          ? [
              { key: 'roster', label: 'Roster', players: starters },
              { key: 'ir', label: 'IR', players: irBench },
              { key: 'taxi', label: 'Taxi', players: taxiBench },
            ]
          : [
              { key: 'starters', label: 'Starters', players: starters },
              { key: 'bench', label: 'Bench', players: activeBench },
              { key: 'ir', label: 'IR', players: irBench },
              { key: 'taxi', label: 'Taxi', players: taxiBench },
            ],
  );

  const goToPlayer = useCallback(
    (player: LineupPlayer) => {
      navigation.navigate('PlayerDetail', { player: toRankedPlayer(player), leagueId, leagueName });
    },
    [navigation, leagueId, leagueName],
  );

  if (loading) {
    return (
      <View style={styles.root}>
        <GridBackground />
        <ScrollView
          style={styles.container}
          contentContainerStyle={[styles.content, { paddingBottom: orbClearance, paddingTop: headerHeight }]}
        >
          <SkeletonCard rows={4} />
          <SkeletonCard rows={4} />
          <AnimatedCard style={styles.skeletonList}>
            <SkeletonRows count={7} />
          </AnimatedCard>
          <SkeletonCard rows={2} />
        </ScrollView>
      </View>
    );
  }

  if (error) {
    return (
      <View style={[styles.center, { paddingTop: headerHeight }]}>
        <ErrorState title="Couldn't load My Team" message={error} onRetry={() => void myTeamQuery.refetch()} />
      </View>
    );
  }

  if (notice) {
    return (
      <View style={[styles.center, { paddingTop: headerHeight }]}>
        <AppText style={styles.notice}>{notice}</AppText>
      </View>
    );
  }

  const rosterTabs: { key: RosterTabKey; label: string; players: LineupPlayer[] }[] = bestBall
    ? [{ key: 'starters', label: 'Roster', players: starters }]
    : [
        { key: 'starters', label: 'Starters', players: starters },
        { key: 'bench', label: 'Bench', players: activeBench },
      ];
  if (irBench.length > 0) rosterTabs.push({ key: 'ir', label: 'IR', players: irBench });
  if (taxiBench.length > 0) rosterTabs.push({ key: 'taxi', label: 'Taxi', players: taxiBench });
  const currentTab = rosterTabs.find((tab) => tab.key === rosterTab) ?? rosterTabs[0];

  return (
    <View style={styles.root}>
      <GridBackground />
      <ScrollView style={styles.container} contentContainerStyle={[styles.content, { paddingBottom: orbClearance, paddingTop: headerHeight }]}>
        <BrandHeaderBar leagueId={leagueId} leagueName={leagueName} />

        <SectionHeading title="Team Snapshot" topGap={12} />
        <TeamSnapshot team={myTeam} leagueSize={leagueSize} teamValue={teamValue} />
        {myTeam && hasRosterAnalysis(myTeam) ? (
          <TouchableOpacity
            style={styles.headerLink}
            onPress={() => setShowFullAnalysis((v) => !v)}
            activeOpacity={0.7}
            hitSlop={6}
          >
            <AppText style={styles.linkRowText}>{showFullAnalysis ? 'Hide team analytics' : 'Team analytics'}</AppText>
            <Ionicons name={showFullAnalysis ? 'chevron-up' : 'chevron-forward'} size={13} color={colors.accent} />
          </TouchableOpacity>
        ) : null}
        {showFullAnalysis && myTeam ? (
          <TeamAnalysisPanel
            team={myTeam}
            leagueSize={leagueSize}
            showExplanations={false}
            onOpenTeams={() => navigation.navigate('Teams', { leagueId, leagueName })}
            onOpenFranchise={() => navigation.navigate('Teams', { leagueId, leagueName, metric: 'franchise' })}
            onOpenDraftCenter={() => navigation.navigate('DraftCenter', { leagueId, leagueName })}
            onOpenStarters={() => setRosterTab('starters')}
            onOpenBench={() => setRosterTab('bench')}
            onOpenAge={() => navigation.navigate('Teams', { leagueId, leagueName, metric: 'age' })}
          />
        ) : null}

        {analysisRows.length > 0 ? (
          <>
            <SectionHeading title="Team Analysis" topGap={12} />
            <TeamAnalysisRows rows={analysisRows} />
          </>
        ) : null}

        <SectionHeading
          title="Your Roster"
          topGap={12}
          right={
            !bestBall && startersValue > 0 ? (
              <AppText style={styles.sectionTotal}>{`Starters Value ${Math.round(startersValue).toLocaleString()}`}</AppText>
            ) : undefined
          }
        />
        {bestBall && myTeamData?.lineup_advice_message ? (
          <AppText style={styles.bestBallNote}>{myTeamData.lineup_advice_message}</AppText>
        ) : null}
        <View style={styles.tabBar}>
          <SegmentedTabBar options={rosterTabs} active={currentTab.key} onChange={setRosterTab} />
        </View>
        {currentTab.key === 'starters' && !bestBall && openSlotsMessage(myTeamData?.open_slots) ? (
          <AppText style={[styles.disclaimer, { color: colors.premium }]}>{openSlotsMessage(myTeamData?.open_slots)}</AppText>
        ) : null}
        {currentTab.players.length === 0 ? (
          <AppText style={styles.rosterEmpty}>
            {currentTab.key === 'starters' ? 'No suggested starters yet.' : 'Nobody here yet.'}
          </AppText>
        ) : (
          <AnimatedCard style={styles.groupCard}>
            {currentTab.players.map((player, index) => (
              <LineupRow
                key={player.player_id}
                player={player}
                keeper={keepers?.players?.[player.player_id]}
                showDivider={index < currentTab.players.length - 1}
                onPress={() => goToPlayer(player)}
                muted={currentTab.key !== 'starters'}
              />
            ))}
          </AnimatedCard>
        )}
        <KeeperCandidatesSection keepers={keepers} />

        {composition.length > 0 ? (
          <>
            <SectionHeading title="Roster Composition" topGap={12} />
            <RosterCompositionBar segments={composition} />
          </>
        ) : null}
        <ValuesCredit />
      </ScrollView>
    </View>
  );
}

/** Ring + archetype pill + Team Value total, then the six rank tiles. */
function TeamSnapshot({
  team,
  leagueSize,
  teamValue,
}: {
  team: TeamRanking | null;
  leagueSize: number;
  teamValue: number;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const valuePercentile = team ? percentileFromRank(team.power_rank, leagueSize) : null;
  const outlook = team ? team.archetype_label || team.strategy_label : null;
  const ringColor = valuePercentile != null ? percentileColor(valuePercentile, colors) : colors.accent;
  const record = team
    ? `${team.wins ?? 0}-${team.losses ?? 0}${team.ties ? `-${team.ties}` : ''}`
    : '—';
  const rank = (value: number | null | undefined, tied: boolean | undefined) =>
    value != null ? formatRank(value, Boolean(tied)) : '—';
  return (
    <AnimatedCard>
      <View style={styles.analyticsHeaderRow}>
        <CircularProgressRing
          percent={valuePercentile ?? 0}
          size={84}
          strokeWidth={8}
          color={ringColor}
          valueLabel={valuePercentile != null ? String(valuePercentile) : '—'}
        />
        <View style={styles.analyticsHeaderText}>
          {outlook ? (
            <View style={styles.outlookBadge}>
              <AppText style={styles.outlookBadgeText}>{outlook.toUpperCase()}</AppText>
            </View>
          ) : null}
          <AppText style={styles.teamValueLabel}>TEAM VALUE</AppText>
          <AppText style={styles.teamValueNumber}>{teamValue > 0 ? Math.round(teamValue).toLocaleString() : '—'}</AppText>
        </View>
      </View>
      <View style={styles.analyticsMetricsRow}>
        <DashboardStatRow
          items={[
            { label: 'Record', icon: 'ribbon-outline', value: record },
            { label: 'Power Rank', icon: 'flash-outline', value: rank(team?.power_rank, team?.power_rank_tied) },
            { label: 'Franchise Rank', icon: 'star-outline', value: rank(team?.franchise_rank, team?.franchise_rank_tied) },
          ]}
        />
      </View>
      <DashboardStatRow
        items={[
          { label: 'Starter Strength', icon: 'american-football-outline', value: rank(team?.starter_rank, team?.starter_rank_tied) },
          { label: 'Bench Strength', icon: 'people-outline', value: rank(team?.bench_rank, team?.bench_rank_tied) },
          { label: 'Avg Age', icon: 'hourglass-outline', value: team?.average_age != null ? team.average_age.toFixed(1) : '—' },
        ]}
      />
    </AnimatedCard>
  );
}

/** One row per position room; tap to expand the full sentence. */
function TeamAnalysisRows({ rows }: { rows: TeamAnalysisRow[] }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [open, setOpen] = useState<string | null>(null);
  return (
    <AnimatedCard style={styles.groupCard}>
      {rows.map((row, index) => {
        const isOpen = open === row.position;
        return (
          <View key={row.position} style={index < rows.length - 1 ? styles.compactDivider : undefined}>
            <TouchableOpacity
              style={styles.analysisRow}
              onPress={() => setOpen(isOpen ? null : row.position)}
              activeOpacity={0.7}
              accessibilityRole="button"
              accessibilityState={{ expanded: isOpen }}
            >
              <PositionBadge position={row.position} />
              <View style={[styles.analysisDot, { backgroundColor: ANALYSIS_TONE_COLOR(row.tone, colors) }]} />
              <AppText style={styles.analysisStatus}>{row.status}</AppText>
              <Ionicons name={isOpen ? 'chevron-down' : 'chevron-forward'} size={16} color={colors.textTertiary} />
            </TouchableOpacity>
            {isOpen ? <AppText style={styles.analysisBody}>{row.body}</AppText> : null}
          </View>
        );
      })}
    </AnimatedCard>
  );
}

function RosterCompositionBar({ segments }: { segments: CompositionSegment[] }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const colorFor = (key: string) =>
    key === 'bench' ? colors.textSecondary : key === 'ir' ? colors.danger : key === 'taxi' ? colors.premium : colors.accent;
  return (
    <AnimatedCard>
      <View
        style={styles.compBar}
        accessible
        accessibilityLabel={segments.map((s) => `${s.label} ${s.percent}%`).join(', ')}
      >
        {segments.map((segment) => (
          <View key={segment.key} style={{ width: `${segment.percent}%`, backgroundColor: colorFor(segment.key) }} />
        ))}
      </View>
      <View style={styles.compLegend}>
        {segments.map((segment) => (
          <View key={segment.key} style={styles.compLegendItem}>
            <View style={[styles.compDot, { backgroundColor: colorFor(segment.key) }]} />
            <AppText style={styles.compLegendText}>{segment.label}</AppText>
            <AppText style={styles.compLegendPct}>{`${segment.percent}%`}</AppText>
          </View>
        ))}
      </View>
    </AnimatedCard>
  );
}

/**
 * One roster row — canonical PlayerIdentityRow for identity plus a trailing
 * Value/OVR column, matching TeamRosterScreen's RosterPlayerRow exactly
 * (Magna Carta §19, §47) rather than a third bespoke player-row layout.
 *
 * Injury severity: `injury_label`/`ruled_out` stay server-resolved (IR/PUP
 * arrives on `status` with `injury_status` blank — see LineupPlayer's own
 * doc comment — and `ruled_out` already encodes the roster-context nuance
 * of "kept as a starter because nothing else was available"), but the
 * risk-vs-watch *tone* is derived the same way Waivers/Players/GmTargets/
 * TeamRoster already derive it (`waiverInjuryDisplay`) instead of always
 * defaulting to the harsher 'risk' red. Brief §12 asks specifically whether
 * an injury pill and a red-toned tier badge (IMPACT STARTER) could read as
 * the same thing: PlayerIdentityRow's TierBadge is a bordered, translucent
 * chip in the meta row and the injury pill is a borderless solid chip in
 * the name row (different shape, different row — and, since the
 * color-system audit's 2026-10-03 playerTier follow-up re-hued
 * `impact_starter` off the danger-red lane entirely, now a different hue
 * too: F06233/AE3013 copper vs FF4D4D/D92D2D red dark/light, see
 * playerTier.ts) so they were already visually distinct even before that
 * fix; the real gap here was "Questionable" always rendering in the same
 * red family as a genuine Out/IR status instead of the calmer amber
 * `watch` tone the semantic color system calls for. MatchupScreen's
 * lineup rows share this exact LineupPlayer shape and have the identical
 * gap — worth the same fix there in a follow-up pass.
 */
function LineupRow({
  player,
  onPress,
  showDivider,
  muted = false,
  keeper,
}: {
  keeper?: KeeperPlayerInfo;
  player: LineupPlayer;
  onPress: () => void;
  showDivider: boolean;
  muted?: boolean;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  // A bye-week player (benched by the server's weekly lineup) shows a
  // "Bye" pill in the calmer watch tone; a real injury label always wins.
  const injuryTone = isByeOnlyLabel(player) ? 'watch' : waiverInjuryDisplay(player.injury_status).tone;
  return (
    <PlayerIdentityRow
      playerId={player.player_id}
      name={player.name}
      position={player.position}
      team={player.team}
      tier={player.tier}
      overallRating={player.overall_rating}
      slot={player.slot === 'BENCH' ? player.position : player.slot}
      opportunityLabel={player.opportunity_label}
      // injury_label, not injury_status: IR/PUP/season-ending arrives on
      // `status` with `injury_status` blank, and an injury_status-driven
      // pill hides exactly those players. See LineupPlayer.injury_label.
      injuryLabel={lineupStatusLabel(player)}
      ruledOut={player.ruled_out}
      injuryTone={injuryTone}
      trailingValue={player.score != null ? String(Math.round(player.score)) : '\u2014'}
      trailingCaption="VALUE"
      trailingTone={muted ? 'muted' : 'accent'}
      trailingExtra={
        <>
          {keeper?.is_keeper ? <ToneBadge label="Keeper" color={colors.accent} /> : null}
          {keeper?.surplus != null && keeper.cost_round != null ? (
            <AppText style={styles.valueLabel}>
              {`${keeper.kept_round ? 'R' : '~R'}${keeper.cost_round} ${keeper.surplus > 0 ? '+' : ''}${keeper.surplus}`}
            </AppText>
          ) : null}
        </>
      }
      chevron
      showDivider={showDivider}
      onPress={onPress}
    />
  );
}

const KEEPER_BASIS_LABEL: Record<string, string> = {
  league_setting: 'from the league setting',
  previous_draft: "from last year's draft keepers",
  declared_keepers: 'from your declared keepers',
};

/** Keep-or-cut candidates ranked by estimated surplus (keeper leagues only). */
function KeeperCandidatesSection({ keepers }: { keepers: KeepersResponse | null }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const candidates = keepers?.candidates ?? [];
  if (!keepers || candidates.length === 0) return null;
  return (
    <View>
      <SectionHeading title="Keeper candidates" topGap={12} />
      <AppText style={styles.disclaimer}>
        {`Keep up to ${keepers.keep_count} ${KEEPER_BASIS_LABEL[keepers.keep_count_basis ?? ''] ?? ''}. Rounds and surplus are estimates.`}
      </AppText>
      <AnimatedCard style={styles.groupCard}>
        {candidates.map((c, index) => (
          <View
            key={c.player_id}
            style={[styles.compactRow, index < candidates.length - 1 && styles.compactDivider]}
          >
            <View style={styles.compactIdentity}>
              <PlayerIdentityRow
                playerId={c.player_id}
                name={c.name}
                position={c.position}
                team={c.team}
                slot={c.reason}
                showDivider={false}
              />
            </View>
            {keepers.recommended_ids?.includes(c.player_id) ? (
              <ToneBadge label="Keep" color={colors.success} />
            ) : null}
          </View>
        ))}
      </AnimatedCard>
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
  headerButtonRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  root: { flex: 1, backgroundColor: colors.background },
  container: { flex: 1, backgroundColor: 'transparent' },
  content: { padding: spacing.lg, paddingBottom: spacing.xl * 4 },
  tabBar: { marginBottom: spacing.sm },
  skeletonList: { padding: spacing.md, marginTop: spacing.sm, marginBottom: spacing.sm },
  analysisRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, paddingVertical: spacing.sm },
  analysisDot: { width: 10, height: 10, borderRadius: 5 },
  analysisStatus: { flex: 1, fontSize: 14, fontWeight: '700', color: colors.textPrimary },
  analysisBody: { fontSize: 13, color: colors.textSecondary, lineHeight: 18, paddingBottom: spacing.sm },
  analysisNotes: { marginTop: spacing.sm },
  teamValueLabel: { fontSize: 10, fontWeight: '700', color: colors.textTertiary, letterSpacing: 0.5 },
  teamValueNumber: { fontSize: 24, fontWeight: '800', color: colors.textPrimary },
  compBar: { flexDirection: 'row', height: 12, borderRadius: 6, overflow: 'hidden', marginBottom: spacing.md },
  compLegend: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.md },
  compLegendItem: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  compDot: { width: 8, height: 8, borderRadius: 4 },
  compLegendText: { fontSize: 12, color: colors.textSecondary },
  compLegendPct: { fontSize: 12, fontWeight: '800', color: colors.textPrimary },
  rosterEmpty: { fontSize: 13, color: colors.textTertiary, paddingVertical: spacing.md },
  center: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.background,
    padding: spacing.xl,
  },
  disclaimer: { fontSize: 12, color: colors.textTertiary, lineHeight: 17, marginBottom: spacing.md },
  analyticsHeaderRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.lg },
  analyticsRingWrap: { alignItems: 'center' },
  analyticsRingCaption: {
    fontSize: 10,
    fontWeight: '700',
    color: colors.textTertiary,
    letterSpacing: 0.5,
    marginTop: spacing.xs,
  },
  analyticsTeamAvatar: { borderWidth: 2, borderColor: colors.accent },
  analyticsHeaderText: { flex: 1, gap: spacing.xs },
  // Solid cyan fill + near-black text, matching coridian_'s concept mockup
  // exactly (a translucent accentMuted chip with cyan text read as a plain
  // outline pill there, not the bold filled badge the concept shows) — same
  // solid-accent-pill pattern LeagueDetailScreen's "YOU" badge already uses
  // (Magna Carta §3: cyan = GM intelligence/analytical emphasis, at its
  // strongest here since the archetype label is this card's headline call-out).
  outlookBadge: {
    alignSelf: 'flex-start',
    backgroundColor: colors.accent,
    borderRadius: radii.pill,
    paddingHorizontal: spacing.sm + 2,
    paddingVertical: 4,
  },
  outlookBadgeText: { fontSize: 11, fontWeight: '800', color: colors.onAccent, letterSpacing: 0.4 },
  analyticsRankLine: { fontSize: 13, color: colors.textSecondary },
  analyticsMetricsRow: {
    flexDirection: 'row',
    flexWrap: 'nowrap',
    gap: spacing.sm,
    marginTop: spacing.lg,
    paddingTop: spacing.md,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.border,
  },
  // Forces exactly three tiles into one compact row (concept mockup) instead
  // of MetricCard's default `minWidth: '46%'`, which is tuned for a 2-up
  // grid and would wrap a 3rd tile onto its own oversized row here.
  analyticsMetricTile: { flexBasis: 0, flexGrow: 1, minWidth: 0, paddingHorizontal: spacing.sm },
  sectionTotal: { fontSize: 11, fontWeight: '700', color: colors.accent, letterSpacing: 0.4 },
  headerLink: { flexDirection: 'row', alignItems: 'center', gap: 2 },
  // One grouped surface per lineup section (Starters, Bench) with a
  // PlayerIdentityRow per player and hairline dividers between them,
  // instead of a separately bordered/backgrounded card per player — see
  // Magna Carta §12 (card philosophy) and MatchupScreen's StarterSection,
  // which established this exact grouped-card pattern first.
  groupCard: { padding: spacing.md, paddingVertical: spacing.xs },
  compactRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: spacing.xs,
    gap: spacing.sm,
  },
  compactDivider: { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border },
  compactIdentity: { flex: 1 },
  valueLabel: { fontSize: 9, fontWeight: '700', color: colors.textTertiary, letterSpacing: 0.4 },
  linkRowText: { fontSize: 13, fontWeight: '700', color: colors.accent },
  notice: { textAlign: 'center', color: colors.textSecondary, lineHeight: 20 },
  bestBallNote: { color: colors.textSecondary, lineHeight: 20, marginBottom: spacing.md },
  error: { color: colors.danger, textAlign: 'center' },
  });
}
