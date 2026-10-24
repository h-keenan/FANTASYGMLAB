import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { ScrollView, StyleSheet, TouchableOpacity, View } from 'react-native';
import AppText from '../components/AppText';
import ErrorState from '../components/ErrorState';
import { useFocusEffect } from '@react-navigation/native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useHeaderHeight } from '@react-navigation/elements';
import { Ionicons } from '@expo/vector-icons';
import { useIsRestoring, useQuery, useQueryClient } from '@tanstack/react-query';

import BeginnerHelp from '../components/BeginnerHelp';
import EmptyState from '../components/EmptyState';
import AnimatedCard from '../components/AnimatedCard';
import EvaluationLensHeaderButton from '../components/EvaluationLensHeaderButton';
import GmStanceHeaderButton from '../components/GmStanceHeaderButton';
import LeagueSwitcherHeaderButton from '../components/LeagueSwitcherHeaderButton';
import BrandHeaderBar from '../components/BrandHeaderBar';
import BrandedSpinner from '../components/BrandedSpinner';
import { PlannerBar, SwapSheet, useLineupPlanner } from '../components/MatchupPlanner';
import GuillotineCard from '../components/GuillotineCard';
import GridBackground from '../components/GridBackground';
import PlayerAvatar from '../components/PlayerAvatar';
import PositionBadge from '../components/PositionBadge';
import SectionHeading from '../components/SectionHeading';
import SegmentedTabBar from '../components/SegmentedTabBar';
import DashboardStatRow from '../components/DashboardStatRow';
import TeamAvatar from '../components/TeamAvatar';
import ToneBadge from '../components/ToneBadge';
import ValuesCredit from '../components/ValuesCredit';
import {
  api,
  type MatchupPositionEdge,
  type MatchupResponse,
  type MatchupSide,
  type MatchupSuggestedMove,
} from '../lib/api';
import {
  edgeExplanation,
  formatSeasonValue,
  formatSigned,
  hasKickedOff,
  lineupComparisonRows,
  lineupPlayerPoints,
  matchupActionLabel,
  matchupNextAction,
  matchupVerdict,
  moveOverLine,
  moveSlotLabel,
  recordLabel,
  winProbabilityUnavailableMessage,
  type LineupPlayer,
  type VerdictTone,
} from '../lib/matchupPresentation';
import { emptySlotsOf, plannerBase, plannerOpponentPlayers, slotIndexFor, winPercent } from '../lib/matchupPlanner';
import { useOrbClearance } from '../lib/orbLayout';
import { queryKeys } from '../lib/queryKeys';
import { useScreenHeaderTitle } from '../lib/useScreenHeaderTitle';
import { toUserErrorMessage } from '../lib/errorMessages';
import { useThemeMode } from '../context/ThemeModeContext';
import { radii, spacing, type ThemeColors } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';
import { usePlayerQuickView } from '../context/PlayerQuickViewContext';

type Props = NativeStackScreenProps<RootStackParamList, 'Matchup'>;

/**
 * Weekly Matchup, laid out to the owner's concept (2026-10-21): header with
 * week + LIVE, scoreboard, Matchup Insights, Lineup Comparison with
 * Suggested | Actual tabs, Suggested Moves. Every number comes from
 * GET .../leagues/{id}/matchup (the same payload the web page reads); the
 * helpers in lib/matchupPresentation only format it. FantasyDesk can't set
 * a Sleeper lineup, so Suggested is a planner. "Edit lineup" turns the
 * user's own column into a swap planner (components/MatchupPlanner.tsx);
 * every number for an edited lineup comes from POST .../matchup/what-if.
 */

const NOT_READY_MESSAGES: Record<string, string> = {
  no_sleeper_username_linked:
    'Link your Sleeper username on the web app first — the matchup view needs to know which roster is yours.',
  sleeper_user_not_found: "Couldn't find that Sleeper account. Double-check the linked username on the web app.",
  not_a_member_of_league: "You don't appear to own a team in this league.",
  empty_roster: "This roster doesn't have any players yet.",
  no_player_data: "Player data isn't available right now — try again in a bit.",
  no_current_week: "This league hasn't started a week yet.",
  no_matchup_data: "Sleeper doesn't have matchups posted for this week yet.",
  roster_not_in_matchups: "Your roster isn't in this week's matchup list.",
  bye_week: "You're not paired against anyone this week — enjoy the bye.",
  opponent_roster_missing: "Couldn't load your opponent's roster right now — try again in a bit.",
};

const MOVES_PREVIEW_COUNT = 3;

type LineupView = 'suggested' | 'actual';

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
    opportunity_label: player.opportunity_label ?? null,
  };
}

function signedTone(value: number | null | undefined): VerdictTone {
  if (value == null || Math.abs(value) < 0.05) return 'neutral';
  return value > 0 ? 'positive' : 'risk';
}

function toneColor(colors: ThemeColors, tone: VerdictTone): string {
  if (tone === 'positive') return colors.successBright;
  if (tone === 'risk') return colors.danger;
  return colors.textSecondary;
}

export default function MatchupScreen({ route, navigation }: Props) {
  const { openPlayer: openQuickView } = usePlayerQuickView();
  const orbClearance = useOrbClearance();
  const headerHeight = useHeaderHeight();
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const { leagueId, leagueName } = route.params;
  const queryClient = useQueryClient();
  const isRestoring = useIsRestoring();
  // Shares its cache entry with DashboardScreen's own matchup fetch.
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
  const matchup: MatchupResponse | null = matchupQuery.data ?? null;
  const loading = isRestoring || matchupQuery.isPending;
  const error =
    matchupQuery.isError && !matchup
      ? toUserErrorMessage(matchupQuery.error, 'Failed to load this week’s matchup.')
      : null;
  const [view, setView] = useState<LineupView | null>(null);
  const planner = useLineupPlanner(leagueId, matchupQuery.data ?? ({ best_ball: true } as MatchupResponse));
  const edited = planner.plan?.result;

  useScreenHeaderTitle(navigation, 'Matchup', leagueName);

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
      void queryClient.invalidateQueries({ queryKey: queryKeys.matchup(leagueId) });
    }, [queryClient, leagueId]),
  );

  if (loading) {
    return <BrandedSpinner style={[styles.center, { paddingTop: headerHeight }]} />;
  }

  if (error) {
    return (
      <View style={[styles.center, { paddingTop: headerHeight }]}>
        <ErrorState title="Couldn't load your matchup" message={error} onRetry={() => void matchupQuery.refetch()} />
      </View>
    );
  }

  if (guillotine) {
    // Guillotine leagues have no head-to-head: survival replaces win probability.
    return (
      <View style={styles.root}>
        <GridBackground />
        <ScrollView
          style={styles.container}
          contentContainerStyle={[styles.content, { paddingBottom: orbClearance, paddingTop: headerHeight }]}
        >
          <BrandHeaderBar leagueId={leagueId} leagueName={leagueName} />
          <View style={styles.titleRow}>
            <AppText style={styles.title}>Matchup</AppText>
            {guillotine.week != null ? <AppText style={styles.weekLabel}>Week {guillotine.week}</AppText> : null}
          </View>
          <GuillotineCard data={guillotine} />
        </ScrollView>
      </View>
    );
  }

  if (!matchup || !matchup.my_team || !matchup.opponent || !matchup.comparison) {
    const reason = matchup?.reason ?? '';
    const next = matchupNextAction(reason);
    const onNext = () => {
      if (next.action === 'retry') void matchupQuery.refetch();
      else if (next.action === 'connect') navigation.navigate('Home', { openAddLeague: true });
      else navigation.navigate('Dashboard', { leagueId, leagueName });
    };
    return (
      <View style={[styles.center, { paddingTop: headerHeight }]}>
        <EmptyState
          icon="calendar-outline"
          title={NOT_READY_MESSAGES[reason] ?? "Couldn't build this week's matchup for this league yet."}
          subtitle={next.subtitle}
          actionLabel={matchupActionLabel(next.action)}
          onPressAction={onNext}
        />
      </View>
    );
  }

  const mine = matchup.my_team;
  const opponent = matchup.opponent;
  const bestBall = matchup.best_ball === true;
  const activeView: LineupView = bestBall ? 'actual' : (view ?? (mine.has_live_data ? 'actual' : 'suggested'));
  // While planning, the scoreboard and position edges show the edited
  // lineup (the API's numbers); everything else stays the real matchup.
  const shown: MatchupResponse = edited?.win_probability
    ? {
        ...matchup,
        win_probability: edited.win_probability,
        position_edges: { actual: edited.position_edges ?? null, suggested: edited.position_edges ?? [] },
      }
    : matchup;
  const openPlayer = (player: LineupPlayer) =>
    openQuickView(toRankedPlayer(player), { leagueId, leagueName });

  return (
    <View style={styles.root}>
      <GridBackground />
      <ScrollView
        style={styles.container}
        contentContainerStyle={[styles.content, { paddingBottom: orbClearance, paddingTop: headerHeight }]}
      >
        <BrandHeaderBar leagueId={leagueId} leagueName={leagueName} />
        <View style={styles.titleRow}>
          <AppText style={styles.title}>Matchup</AppText>
          {matchup.week != null ? <AppText style={styles.weekLabel}>Week {matchup.week}</AppText> : null}
          {matchup.game_state === 'live' ? (
            <View style={styles.liveBadge} accessibilityLabel="Games in progress">
              <View style={styles.liveDot} />
              <AppText style={styles.liveBadgeText}>LIVE</AppText>
            </View>
          ) : null}
        </View>

        <BeginnerHelp term="matchupIntro" />
        <BeginnerHelp term="matchupWinProbability" />
        <Scoreboard matchup={shown} mine={mine} opponent={opponent} />
        {matchup.unmapped_players && matchup.unmapped_players.length > 0 ? (
          <AppText style={{ color: colors.textSecondary, fontSize: 12 }}>
            {`Not matched to a FantasyDesk player, so left out of the lineups and win odds: ${matchup.unmapped_players
              .map((p) => `${p.name} (${p.fantasy_team})`)
              .join(', ')}.`}
          </AppText>
        ) : null}
        <Insights matchup={shown} />
        <LineupComparison
          matchup={matchup}
          view={activeView}
          onViewChange={setView}
          onPressPlayer={openPlayer}
          leagueId={leagueId}
          planner={planner}
        />
        {planner.sheet && planner.plan ? (
          <SwapSheet
            sheet={planner.sheet}
            slot={planner.plan.slots[planner.sheet.index]?.slot ?? ''}
            onPick={planner.pick}
            onClose={planner.closeSheet}
          />
        ) : null}
        {bestBall ? (
          // Best ball: Sleeper sets both lineups from the highest weekly
          // scorers, so there is no suggested lineup or start/sit call.
          <AppText style={styles.bestBallNote}>{matchup.lineup_advice_message}</AppText>
        ) : (
          <SuggestedMoves matchup={matchup} />
        )}
        <ValuesCredit />
      </ScrollView>
    </View>
  );
}

function ScoreSide({
  side,
  accent,
  score,
  projected,
  kickedOff,
}: {
  side: MatchupSide;
  accent: string;
  score: number | null;
  projected: number | null;
  kickedOff: boolean;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  // Pre-kickoff, Sleeper's 0.0 isn't a score yet: the projection leads.
  const live = kickedOff && score != null;
  const headline = live ? score!.toFixed(1) : projected != null ? projected.toFixed(1) : '—';
  const caption = live ? (projected != null ? `Proj ${projected.toFixed(1)}` : null) : 'Projected';
  return (
    <View style={styles.scoreSide}>
      <TeamAvatar
        avatarId={side.avatar_url}
        size={56}
        style={StyleSheet.flatten([styles.scoreAvatar, { borderColor: accent }])}
      />
      <AppText style={styles.scoreTeam} numberOfLines={2}>
        {side.team_name}
      </AppText>
      <AppText style={styles.scoreRecord}>{recordLabel(side)}</AppText>
      <AppText style={styles.scoreValue}>{headline}</AppText>
      {caption ? <AppText style={styles.scoreCaption}>{caption}</AppText> : null}
    </View>
  );
}

function Scoreboard({
  matchup,
  mine,
  opponent,
}: {
  matchup: MatchupResponse;
  mine: MatchupSide;
  opponent: MatchupSide;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const comparison = matchup.comparison!;
  const odds = matchup.win_probability;
  const hasOdds = odds?.available === true && odds.probability != null;
  const myPct = hasOdds ? Math.round(odds!.probability! * 100) : null;
  const myProjected = hasOdds ? (odds!.my_projected_total ?? null) : null;
  const opponentProjected = hasOdds ? (odds!.opponent_projected_total ?? null) : null;
  const margin = myProjected != null && opponentProjected != null ? myProjected - opponentProjected : null;
  const kickedOff = hasKickedOff(matchup);

  return (
    <AnimatedCard glow style={styles.card}>
      <View style={styles.scoreRow}>
        <ScoreSide
          side={mine}
          accent={colors.accent}
          score={mine.has_live_data ? mine.real_points : null}
          projected={myProjected}
          kickedOff={kickedOff}
        />
        <AppText style={styles.vs}>VS</AppText>
        <ScoreSide
          side={opponent}
          accent={colors.violet}
          score={opponent.has_live_data ? opponent.real_points : null}
          projected={opponentProjected}
          kickedOff={kickedOff}
        />
      </View>

      {hasOdds ? (
        <View style={styles.oddsBlock}>
          <View
            style={styles.oddsTrack}
            accessible
            accessibilityLabel={`Win probability: you ${myPct}%, opponent ${100 - myPct!}%.`}
          >
            <View style={[styles.oddsFill, { width: `${myPct ?? 0}%` }]} />
          </View>
          <View style={styles.oddsLabels}>
            <AppText style={[styles.oddsPct, { color: colors.successBright }]}>{myPct}%</AppText>
            <AppText style={styles.oddsCaption}>WIN PROBABILITY</AppText>
            <AppText style={[styles.oddsPct, { color: colors.textSecondary }]}>{100 - myPct!}%</AppText>
          </View>
        </View>
      ) : (
        <AppText style={styles.oddsUnavailable}>{winProbabilityUnavailableMessage(matchup)}</AppText>
      )}

      <DashboardStatRow
        style={{ marginBottom: 0 }}
        items={[
          { label: 'Your value', value: formatSeasonValue(comparison.my_season_value) },
          {
            label: 'Proj margin',
            value: margin != null ? formatSigned(margin) : '—',
            tone: margin != null && signedTone(margin) !== 'neutral' ? (signedTone(margin) as 'positive' | 'risk') : undefined,
          },
          { label: 'Their value', value: formatSeasonValue(comparison.opponent_season_value) },
          {
            label: 'Value margin',
            value:
              comparison.margin === 0
                ? '0'
                : `${comparison.margin > 0 ? '+' : '-'}${formatSeasonValue(Math.abs(comparison.margin))}`,
            tone: comparison.edge === 'you' ? 'positive' : comparison.edge === 'opponent' ? 'risk' : undefined,
          },
        ]}
      />
    </AnimatedCard>
  );
}

function Insights({ matchup }: { matchup: MatchupResponse }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const verdict = matchupVerdict(matchup);
  const actualEdges = matchup.position_edges?.actual ?? null;
  const edges: MatchupPositionEdge[] = actualEdges ?? matchup.position_edges?.suggested ?? [];
  const explanation = edgeExplanation(edges);
  const basis = actualEdges
    ? hasKickedOff(matchup)
      ? 'Position edges: your Sleeper lineups, real points for started games plus projections.'
      : 'Position edges: this week’s projections for your Sleeper lineups.'
    : 'Position edges: projections for each team’s suggested lineup (Sleeper lineups aren’t posted yet).';
  return (
    <AnimatedCard style={styles.card}>
      <SectionHeading title="Matchup Insights" icon="sparkles-outline" />
      <View style={styles.insightsRow}>
        <View style={styles.insightsText}>
          <AppText style={[styles.verdict, { color: toneColor(colors, verdict.tone) }]}>{verdict.headline}</AppText>
          <AppText style={styles.insightsBody}>{explanation ?? 'No position projections yet to compare.'}</AppText>
        </View>
        {edges.length ? (
          <View style={styles.edgeList} accessibilityLabel="Position edges">
            {edges.map((edge) => {
              const tone = signedTone(edge.edge);
              const color = toneColor(colors, tone);
              return (
                <View key={edge.position} style={styles.edgeRow}>
                  <Ionicons
                    name={tone === 'positive' ? 'arrow-up' : tone === 'risk' ? 'arrow-down' : 'remove'}
                    size={14}
                    color={color}
                  />
                  <PositionBadge position={edge.position} />
                  <AppText style={[styles.edgeValue, { color }]}>{formatSigned(edge.edge)}</AppText>
                </View>
              );
            })}
          </View>
        ) : null}
      </View>
      <AppText style={styles.footnote}>{basis}</AppText>
    </AnimatedCard>
  );
}

function PointsBar({ value, max, mine }: { value: number | null; max: number; mine: boolean }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const pct = value != null && max > 0 ? Math.max(0, Math.min(100, (value / max) * 100)) : 0;
  return (
    <View style={styles.barTrack}>
      <View
        style={[
          styles.barFill,
          { width: `${pct}%`, backgroundColor: mine ? colors.accent : colors.textTertiary },
          !mine && { alignSelf: 'flex-end' },
        ]}
      />
    </View>
  );
}

function LineupCell({
  player,
  mine,
  maxValue,
  onPress,
  onEdit,
}: {
  player: LineupPlayer | 'empty' | null;
  mine: boolean;
  maxValue: number;
  onPress: (player: LineupPlayer) => void;
  /** Planner mode: tapping the cell opens the swap sheet instead of Player Detail. */
  onEdit?: () => void;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  if (player === null) return <View style={styles.cell} />;
  if (player === 'empty') {
    return onEdit ? (
      <TouchableOpacity style={[styles.cell, styles.cellCenter]} onPress={onEdit} accessibilityRole="button">
        <AppText style={[styles.emptySlot, { color: colors.accent }]}>Empty slot, tap to fill</AppText>
      </TouchableOpacity>
    ) : (
      <View style={[styles.cell, styles.cellCenter]}>
        <AppText style={styles.emptySlot}>Empty slot</AppText>
      </View>
    );
  }
  const points = lineupPlayerPoints(player);
  const valueText = points.value != null ? points.value.toFixed(1) : points.note === 'bye' ? null : '—';
  const align = mine ? 'flex-start' : 'flex-end';
  return (
    <TouchableOpacity
      style={[styles.cell, mine ? styles.cellRow : styles.cellRowReverse]}
      onPress={() => (onEdit ? onEdit() : onPress(player))}
      accessibilityRole="button"
      accessibilityLabel={onEdit ? `Swap ${player.name ?? 'player'}` : `${player.name ?? 'Player'}, ${player.team ?? 'free agent'}`}
    >
      <PlayerAvatar playerId={player.player_id} tier={player.tier} size={30} />
      <View style={[styles.cellBody, { alignItems: align }]}>
        <AppText style={[styles.cellName, !mine && styles.textRight]} numberOfLines={1}>
          {player.name || 'Unknown player'}
        </AppText>
        <View style={[styles.cellMeta, mine ? styles.cellRow : styles.cellRowReverse]}>
          <AppText style={styles.cellTeam} numberOfLines={1}>
            {player.team || 'FA'}
            {player.injury_label ? ` · ${player.injury_label}` : ''}
          </AppText>
          {valueText ? (
            <AppText style={styles.cellPoints}>{valueText}</AppText>
          ) : (
            <ToneBadge label="Bye" color={colors.premium} />
          )}
        </View>
        <PointsBar value={points.value} max={maxValue} mine={mine} />
      </View>
    </TouchableOpacity>
  );
}

function LineupComparison({
  matchup,
  view,
  onViewChange,
  onPressPlayer,
  leagueId,
  planner,
}: {
  matchup: MatchupResponse;
  view: LineupView;
  onViewChange: (view: LineupView) => void;
  onPressPlayer: (player: LineupPlayer) => void;
  leagueId: string;
  planner: ReturnType<typeof useLineupPlanner>;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const mine = matchup.my_team!;
  const opponent = matchup.opponent!;
  const bestBall = matchup.best_ball === true;
  const actual = view === 'actual';
  const plan = planner.plan;
  const canPlan = !bestBall && plannerBase(matchup, view) != null;
  const rows = plan
    ? lineupComparisonRows(
        plan.starters ?? [],
        plannerOpponentPlayers(matchup),
        emptySlotsOf(plan.slots),
        opponent.has_live_data ? (opponent.real_empty_slots ?? []) : (opponent.open_slots ?? []),
      )
    : actual
    ? lineupComparisonRows(
        mine.has_live_data ? mine.real_starters : [],
        opponent.has_live_data ? opponent.real_starters : [],
        mine.real_empty_slots ?? [],
        opponent.real_empty_slots ?? [],
      )
    : lineupComparisonRows(mine.starters, opponent.starters);
  const maxValue = Math.max(
    0,
    ...rows.flatMap((row) =>
      [row.mine, row.opponent].map((cell) => (cell && cell !== 'empty' ? (lineupPlayerPoints(cell).value ?? 0) : 0)),
    ),
  );
  const caption = plan
    ? 'Tap one of your players to see who could take the slot. A planner only: make the final change in Sleeper.'
    : actual
    ? 'Lineups as set in Sleeper.'
    : 'Our best lineup for each team, run the same way for both sides. A planner only: set your lineup in Sleeper.';

  return (
    <AnimatedCard style={styles.card}>
      <SectionHeading title="Lineup Comparison" icon="git-compare-outline" />
      {bestBall || plan ? null : (
        <SegmentedTabBar
          options={[
            { key: 'suggested' as const, label: 'Suggested Lineup' },
            { key: 'actual' as const, label: 'Actual Lineup' },
          ]}
          active={view}
          onChange={onViewChange}
        />
      )}
      {canPlan || plan ? (
        <PlannerBar
          editing={Boolean(plan)}
          busy={plan?.busy ?? false}
          error={plan?.error ?? null}
          baselinePct={plan?.baselinePct ?? null}
          currentPct={winPercent(plan?.result?.win_probability)}
          leagueId={leagueId}
          onEdit={() => planner.start(view)}
          onReset={planner.resetToSuggested}
          onDone={planner.exit}
        />
      ) : null}
      <AppText style={styles.footnote}>
        {caption}
        {hasKickedOff(matchup)
          ? ' Started games show real points; the rest show projections.'
          : ' Numbers are this week’s projections.'}
      </AppText>
      {rows.length === 0 ? (
        <AppText style={styles.emptyNote}>
          {actual ? 'Sleeper hasn’t posted lineups for this week yet.' : 'No startable players on either roster right now.'}
        </AppText>
      ) : (
        <View>
          {rows.map((row, index) => {
            const emptyOrdinal =
              row.mine === 'empty'
                ? rows.slice(0, index).filter((r) => r.slot === row.slot && r.mine === 'empty').length
                : 0;
            const editIndex = plan ? slotIndexFor(plan.slots, row.mine, row.slot, emptyOrdinal) : -1;
            return (
            <View key={`${row.slot}-${index}`} style={styles.tableRow}>
              <LineupCell
                player={row.mine}
                mine
                maxValue={maxValue}
                onPress={onPressPlayer}
                onEdit={plan && editIndex >= 0 ? () => void planner.openSlot(editIndex) : undefined}
              />
              <View style={styles.slotCell}>
                <PositionBadge position={row.slot} />
              </View>
              <LineupCell player={row.opponent} mine={false} maxValue={maxValue} onPress={onPressPlayer} />
            </View>
            );
          })}
        </View>
      )}
    </AnimatedCard>
  );
}

function MoveCard({ move, slotLabel }: { move: MatchupSuggestedMove; slotLabel: string }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const tone = signedTone(move.gain);
  const gainColor = toneColor(colors, tone);
  return (
    <View style={styles.moveCard}>
      <View style={styles.moveSlot}>
        <PositionBadge position={move.slot} label={slotLabel} />
      </View>
      <PlayerAvatar playerId={move.start.player_id} tier={move.start.tier} size={40} />
      <View style={styles.moveBody}>
        <AppText style={styles.moveTitle} numberOfLines={1}>
          <AppText style={{ color: colors.successBright }}>Start </AppText>
          {move.start.name || 'Unknown player'}
        </AppText>
        <AppText style={styles.moveSub} numberOfLines={1}>
          {move.start.points != null ? `Proj ${move.start.points.toFixed(1)}` : 'No projection yet'}
        </AppText>
        <AppText style={styles.moveSub} numberOfLines={2}>
          {moveOverLine(move)}
        </AppText>
      </View>
      <View style={[styles.gainBox, { borderColor: gainColor }]}>
        <AppText style={[styles.gainValue, { color: gainColor }]}>
          {move.gain != null ? formatSigned(move.gain) : '—'}
        </AppText>
        <AppText style={styles.gainCaption}>{move.locked ? 'Locked' : 'Proj pts'}</AppText>
      </View>
    </View>
  );
}

function SuggestedMoves({ matchup }: { matchup: MatchupResponse }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [expanded, setExpanded] = useState(false);
  const moves = matchup.suggested_moves ?? null;
  const actualStarters = matchup.my_team?.real_starters ?? [];
  const shown = moves ? (expanded ? moves : moves.slice(0, MOVES_PREVIEW_COUNT)) : [];
  const hasMore = moves != null && moves.length > MOVES_PREVIEW_COUNT;

  return (
    <AnimatedCard style={styles.card}>
      <SectionHeading
        title="Suggested Moves"
        icon="swap-horizontal-outline"
        right={
          hasMore ? (
            <TouchableOpacity onPress={() => setExpanded((open) => !open)} accessibilityRole="button">
              <AppText style={styles.viewAll}>{expanded ? 'Show fewer' : `View all (${moves!.length})`}</AppText>
            </TouchableOpacity>
          ) : undefined
        }
      />
      {moves === null ? (
        <AppText style={styles.emptyNote}>Suggested moves appear once Sleeper has your lineup for this week.</AppText>
      ) : moves.length === 0 ? (
        <AppText style={styles.emptyNote}>Your Sleeper lineup already matches our suggested lineup.</AppText>
      ) : (
        <View style={styles.moveList}>
          {shown.map((move) => (
            <MoveCard
              key={`${move.start.player_id}-${move.slot}`}
              move={move}
              slotLabel={moveSlotLabel(move, actualStarters)}
            />
          ))}
        </View>
      )}
      <AppText style={styles.footnote}>
        The suggested lineup ranks by season-long value; gains are this week’s projected points. FantasyDesk can’t
        change your Sleeper lineup, so make any swap in Sleeper.
      </AppText>
    </AnimatedCard>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    headerButtonRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
    root: { flex: 1, backgroundColor: 'transparent' },
    container: { flex: 1, backgroundColor: 'transparent' },
    content: { padding: spacing.lg, paddingBottom: spacing.xl * 4, gap: spacing.md },
    center: {
      flex: 1,
      alignItems: 'center',
      justifyContent: 'center',
      backgroundColor: colors.background,
      padding: spacing.xl,
    },
    error: { color: colors.danger, textAlign: 'center' },
    notice: { color: colors.textSecondary, textAlign: 'center', lineHeight: 20 },
    bestBallNote: { color: colors.textSecondary, lineHeight: 20 },
    titleRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
    title: { fontSize: 26, fontWeight: '800', color: colors.textPrimary },
    weekLabel: { fontSize: 14, fontWeight: '700', color: colors.textSecondary },
    liveBadge: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: 4,
      paddingHorizontal: spacing.xs + 2,
      paddingVertical: 2,
      borderRadius: radii.pill,
      backgroundColor: colors.accentMuted,
    },
    liveDot: { width: 6, height: 6, borderRadius: 3, backgroundColor: colors.successBright },
    liveBadgeText: { fontSize: 10, fontWeight: '800', letterSpacing: 0.6, color: colors.successBright },
    card: { padding: spacing.lg, gap: spacing.md },
    scoreRow: { flexDirection: 'row', alignItems: 'center' },
    scoreSide: { flex: 1, alignItems: 'center', gap: 2 },
    scoreAvatar: { borderWidth: 2, marginBottom: spacing.xs },
    scoreTeam: { fontSize: 14, fontWeight: '700', color: colors.textPrimary, textAlign: 'center' },
    scoreRecord: { fontSize: 12, color: colors.textTertiary },
    scoreValue: { fontSize: 30, fontWeight: '800', color: colors.textPrimary, marginTop: spacing.xs },
    scoreCaption: { fontSize: 12, color: colors.textTertiary },
    vs: { fontSize: 12, fontWeight: '800', color: colors.textTertiary, letterSpacing: 1, paddingHorizontal: spacing.xs },
    oddsBlock: { gap: spacing.xs },
    oddsTrack: {
      height: 8,
      borderRadius: radii.pill,
      backgroundColor: colors.border,
      overflow: 'hidden',
    },
    oddsFill: { height: '100%', backgroundColor: colors.accent },
    oddsLabels: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
    oddsPct: { fontSize: 16, fontWeight: '800' },
    oddsCaption: { fontSize: 10, fontWeight: '700', letterSpacing: 0.8, color: colors.textTertiary },
    oddsUnavailable: { fontSize: 12, color: colors.textTertiary, textAlign: 'center' },
    insightsRow: { flexDirection: 'row', gap: spacing.md, alignItems: 'flex-start' },
    insightsText: { flex: 1, gap: spacing.xs },
    verdict: { fontSize: 18, fontWeight: '800' },
    insightsBody: { fontSize: 13, lineHeight: 18, color: colors.textSecondary },
    edgeList: { minWidth: 104, gap: spacing.xs },
    edgeRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs },
    edgeValue: { marginLeft: 'auto', fontSize: 13, fontWeight: '800' },
    footnote: { fontSize: 11, lineHeight: 15, color: colors.textTertiary },
    emptyNote: { fontSize: 13, color: colors.textTertiary, textAlign: 'center', paddingVertical: spacing.md },
    tableRow: {
      flexDirection: 'row',
      alignItems: 'stretch',
      borderBottomWidth: StyleSheet.hairlineWidth,
      borderBottomColor: colors.border,
    },
    cell: { flex: 1, paddingVertical: spacing.sm, minWidth: 0 },
    cellCenter: { justifyContent: 'center' },
    cellRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
    cellRowReverse: { flexDirection: 'row-reverse', alignItems: 'center', gap: 6 },
    cellBody: { flex: 1, gap: 3, minWidth: 0 },
    cellMeta: { justifyContent: 'space-between', alignSelf: 'stretch' },
    cellName: { fontSize: 13, fontWeight: '700', color: colors.textPrimary, alignSelf: 'stretch' },
    textRight: { textAlign: 'right' },
    cellTeam: { fontSize: 11, color: colors.textTertiary, flexShrink: 1 },
    cellPoints: { fontSize: 13, fontWeight: '800', color: colors.textPrimary },
    emptySlot: { fontSize: 12, fontStyle: 'italic', color: colors.textTertiary },
    barTrack: { height: 4, alignSelf: 'stretch', borderRadius: radii.pill, backgroundColor: colors.border, overflow: 'hidden' },
    barFill: { height: '100%' },
    slotCell: {
      width: 44,
      alignItems: 'center',
      justifyContent: 'center',
      marginHorizontal: 4,
    },
    viewAll: { fontSize: 12, fontWeight: '700', color: colors.accent },
    moveList: { gap: spacing.sm },
    moveCard: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: spacing.sm,
      padding: spacing.sm,
      borderRadius: radii.md,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: colors.border,
      backgroundColor: colors.glass,
    },
    moveSlot: { minWidth: 40, alignItems: 'center' },
    moveBody: { flex: 1, gap: 1, minWidth: 0 },
    moveTitle: { fontSize: 14, fontWeight: '700', color: colors.textPrimary },
    moveSub: { fontSize: 12, color: colors.textTertiary },
    gainBox: {
      alignItems: 'center',
      paddingHorizontal: spacing.sm,
      paddingVertical: spacing.xs,
      borderRadius: radii.md,
      borderWidth: StyleSheet.hairlineWidth,
    },
    gainValue: { fontSize: 16, fontWeight: '800' },
    gainCaption: { fontSize: 10, color: colors.textTertiary },
  });
}
