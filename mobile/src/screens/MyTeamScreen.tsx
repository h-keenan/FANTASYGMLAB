import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { ScrollView, StyleSheet, View } from 'react-native';
import AppText from '../components/AppText';
import { useFocusEffect } from '@react-navigation/native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useHeaderHeight } from '@react-navigation/elements';

import AnimatedCard from '../components/AnimatedCard';
import EvaluationLensHeaderButton from '../components/EvaluationLensHeaderButton';
import GmStanceHeaderButton from '../components/GmStanceHeaderButton';
import ScreenHero from '../components/ScreenHero';
import BrandHeaderBar from '../components/BrandHeaderBar';
import BrandedSpinner from '../components/BrandedSpinner';
import CircularProgressRing from '../components/CircularProgressRing';
import GridBackground from '../components/GridBackground';
import PlayerAvatar from '../components/PlayerAvatar';
import { resolvePlayerTier } from '../lib/playerTier';
import PositionBadge from '../components/PositionBadge';
import TeamAvatar from '../components/TeamAvatar';
import { api, type LineupPlayer, type TeamRanking } from '../lib/api';
import { useOrbClearance } from '../lib/orbLayout';
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

/** Best team in the league -> 100, worst -> 0. modules/league_rankings.py
 * only exposes a dense rank (1 = best), never a raw 0-100 score, so a
 * percentile derived from rank position is the honest way to turn "Power
 * Rank #3 of 12" into a ring fill — not a fabricated score. */
function percentileFromRank(rank: number | null, totalTeams: number): number | null {
  if (rank == null || totalTeams <= 1) return null;
  return Math.round(((totalTeams - rank) / (totalTeams - 1)) * 100);
}

function percentileLabel(percentile: number | null): string {
  if (percentile == null) return '—';
  if (percentile >= 67) return 'Strong';
  if (percentile >= 34) return 'Average';
  return 'Light';
}

// Same three buckets PlayersScreen.tsx's own age filter already uses
// (AGE_FILTERS: Under 25 / 25-28 / 29+) — reused here rather than inventing
// a second set of age thresholds for the same underlying concept.
function ageLabel(averageAge: number | null): string {
  if (averageAge == null) return '—';
  if (averageAge < 25) return 'Young';
  if (averageAge <= 28) return 'Prime';
  return 'Aging';
}

export default function MyTeamScreen({ route, navigation }: Props) {
  const orbClearance = useOrbClearance();
  const headerHeight = useHeaderHeight();
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const { leagueId, leagueName } = route.params;
  const [starters, setStarters] = useState<LineupPlayer[]>([]);
  const [bench, setBench] = useState<LineupPlayer[]>([]);
  const [notice, setNotice] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [myTeam, setMyTeam] = useState<TeamRanking | null>(null);
  const [leagueSize, setLeagueSize] = useState(0);

  useScreenHeaderTitle(navigation, 'My Team', leagueName);

  useEffect(() => {
    navigation.setOptions({
      headerRight: () => (
        <View style={styles.headerButtonRow}>
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
          const result = await api.getLeagueMyTeam(leagueId);
          if (cancelled) return;
          setStarters(result.starters);
          setBench(result.bench);
          setNotice(result.reason ? reasonMessage(result.reason) : null);
          // Best-effort, independent of the lineup fetch above — Team
          // Analytics is a bonus section, not core to this screen, so a
          // failure here shouldn't block showing the lineup.
          if (result.roster_id) {
            api
              .getLeagueTeamRankings(leagueId)
              .then((rankings) => {
                if (cancelled) return;
                setLeagueSize(rankings.teams.length);
                setMyTeam(rankings.teams.find((team) => team.roster_id === result.roster_id) ?? null);
              })
              .catch(() => {});
          }
        } catch (err) {
          if (!cancelled) setError(err instanceof Error ? err.message : 'Failed to load your lineup.');
        } finally {
          if (!cancelled) setLoading(false);
        }
      })();
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

  if (notice) {
    return (
      <View style={[styles.center, { paddingTop: headerHeight }]}>
        <AppText style={styles.notice}>{notice}</AppText>
      </View>
    );
  }

  return (
    <View style={styles.root}>
      <GridBackground />
      <ScrollView style={styles.container} contentContainerStyle={[styles.content, { paddingBottom: orbClearance, paddingTop: headerHeight }]}>
        <BrandHeaderBar leagueId={leagueId} leagueName={leagueName} />
        <ScreenHero title="MY TEAM" subtitle={leagueName} />
        <AppText style={styles.disclaimer}>
          Your suggested starting lineup for {leagueName} — the same optimal-lineup logic the web
          app's Dashboard and My Team pages use.
        </AppText>

        {myTeam ? <TeamAnalyticsSection team={myTeam} leagueSize={leagueSize} /> : null}

        <AppText style={styles.sectionLabel}>Starters</AppText>
        {starters.map((player) => (
          <LineupRow
            key={player.player_id}
            player={player}
            onPress={() => navigation.navigate('PlayerDetail', { player: toRankedPlayer(player), leagueId, leagueName })}
          />
        ))}

        <AppText style={styles.sectionLabel}>Bench</AppText>
        {bench.length === 0 ? (
          <AppText style={styles.emptyBench}>No bench players.</AppText>
        ) : (
          bench.map((player) => (
            <LineupRow
              key={player.player_id}
              player={player}
              onPress={() => navigation.navigate('PlayerDetail', { player: toRankedPlayer(player), leagueId, leagueName })}
            />
          ))
        )}
      </ScrollView>
    </View>
  );
}

/**
 * The concept sheet's Panel 4 ("MY TEAM") leads with a team-value ring plus
 * a Key Metrics readout — this screen had no equivalent team-level summary
 * at all before, only the lineup. Every number here is real: Team Value and
 * Draft Capital are percentiles derived from modules/league_rankings.py's
 * own dense ranks (best team in the league -> 100), Roster Age is the real
 * average, and Overall Outlook is the archetype/strategy label
 * modules/team_eval.py already assigns per roster. Two panel-7 items
 * ("Contender Window", a multi-year projected/ceiling/floor chart) are
 * deliberately NOT here — nothing in the backend computes either, and
 * showing invented numbers next to real ones would be worse than showing
 * nothing.
 */
function TeamAnalyticsSection({ team, leagueSize }: { team: TeamRanking; leagueSize: number }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const valuePercentile = percentileFromRank(team.power_rank, leagueSize);
  const draftCapitalPercentile = percentileFromRank(team.draft_capital_rank, leagueSize);
  const starterPercentile = percentileFromRank(team.starter_rank, leagueSize);
  const outlook = team.archetype_label || team.strategy_label;

  const metrics: { label: string; value: string; note: string }[] = [
    {
      label: 'Roster Age',
      value: team.average_age != null ? team.average_age.toFixed(1) : '—',
      note: ageLabel(team.average_age),
    },
    {
      label: 'Draft Capital',
      value: team.draft_capital_rank != null ? `#${team.draft_capital_rank}` : '—',
      note: percentileLabel(draftCapitalPercentile),
    },
  ];

  return (
    <View style={styles.analyticsCard}>
      <View style={styles.analyticsHeaderRow}>
        <View style={styles.analyticsRingWrap}>
          <CircularProgressRing
            percent={valuePercentile ?? 0}
            size={72}
            strokeWidth={7}
            color={colors.accent}
            valueLabel={valuePercentile != null ? String(valuePercentile) : '—'}
          />
          <AppText style={styles.analyticsRingCaption}>TEAM VALUE</AppText>
        </View>
        {team.avatar_url ? (
          <TeamAvatar avatarId={team.avatar_url} size={40} style={styles.analyticsTeamAvatar} />
        ) : null}
        <View style={styles.analyticsHeaderText}>
          {outlook ? (
            <View style={styles.outlookBadge}>
              <AppText style={styles.outlookBadgeText}>{outlook.toUpperCase()}</AppText>
            </View>
          ) : null}
          {team.power_rank != null ? (
            <AppText style={styles.analyticsRankLine}>
              Power Rank #{team.power_rank} of {leagueSize}
            </AppText>
          ) : null}
        </View>
      </View>
      <View style={styles.analyticsMetricsRow}>
        {metrics.map((metric) => (
          <View key={metric.label} style={styles.analyticsMetric}>
            <AppText style={styles.analyticsMetricValue}>{metric.value}</AppText>
            <AppText style={styles.analyticsMetricLabel}>{metric.label}</AppText>
            <AppText style={styles.analyticsMetricNote}>{metric.note}</AppText>
          </View>
        ))}
      </View>
      <View style={styles.analyticsBars}>
        <PercentileBar label="Team Value" percentile={valuePercentile} color={colors.accent} />
        <PercentileBar label="Starter Strength" percentile={starterPercentile} color={colors.success} />
        <PercentileBar label="Draft Capital" percentile={draftCapitalPercentile} color={colors.premium} />
      </View>
    </View>
  );
}

function PercentileBar({ label, percentile, color }: { label: string; percentile: number | null; color: string }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const width = percentile ?? 0;
  return (
    <View style={styles.percentileBarRow}>
      <AppText style={styles.percentileBarLabel} numberOfLines={1}>
        {label}
      </AppText>
      <View style={styles.percentileBarTrack}>
        <View style={[styles.percentileBarFill, { width: `${width}%`, backgroundColor: color }]} />
      </View>
      <AppText style={styles.percentileBarValue}>{percentile != null ? `${percentile}%` : '—'}</AppText>
    </View>
  );
}

function LineupRow({ player, onPress }: { player: LineupPlayer; onPress: () => void }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <AnimatedCard style={styles.card} onPress={onPress}>
      <View style={styles.slotBadge}>
        <AppText style={styles.slotText}>{player.slot === 'BENCH' ? player.position ?? '—' : player.slot}</AppText>
      </View>
      <PlayerAvatar playerId={player.player_id} size={40} tier={player.tier} style={styles.avatar} />
      <View style={styles.nameColumn}>
        <AppText style={styles.name} numberOfLines={1}>
          {player.name ?? 'Unknown player'}
        </AppText>
        <View style={styles.metaRow}>
          <PositionBadge position={player.position} />
          <AppText style={styles.meta} numberOfLines={1}>
            {!player.team && !player.opportunity_label ? (
              '—'
            ) : (
              <>
                {player.team}
                {player.team && player.opportunity_label ? ' · ' : ''}
                {player.opportunity_label ? (
                  <AppText style={[styles.meta, { color: resolvePlayerTier(player.tier).color }]}>
                    {player.opportunity_label}
                  </AppText>
                ) : null}
              </>
            )}
          </AppText>
        </View>
      </View>
      {/* injury_label, not injury_status: IR/PUP/season-ending arrives on
          `status` with `injury_status` blank, and an injury_status-driven
          pill hides exactly those players. See LineupPlayer.injury_label. */}
      {player.injury_label ? (
        <View style={[styles.injuryPill, player.ruled_out && styles.injuryPillOut]}>
          <AppText style={[styles.injuryText, player.ruled_out && styles.injuryTextOut]}>{player.injury_label}</AppText>
        </View>
      ) : null}
      <View style={styles.valueColumn}>
        <AppText style={styles.valueNumber}>{player.score != null ? Math.round(player.score) : '—'}</AppText>
        <AppText style={styles.valueLabel}>VALUE</AppText>
      </View>
    </AnimatedCard>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
  headerButtonRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  root: { flex: 1, backgroundColor: colors.background },
  container: { flex: 1, backgroundColor: 'transparent' },
  content: { padding: spacing.lg, paddingBottom: spacing.xl * 4 },
  center: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.background,
    padding: spacing.xl,
  },
  disclaimer: { fontSize: 12, color: colors.textTertiary, lineHeight: 17, marginBottom: spacing.md },
  analyticsCard: {
    backgroundColor: colors.backgroundElevated,
    borderRadius: radii.lg,
    borderWidth: 1,
    borderColor: colors.cardBorder,
    padding: spacing.lg,
    marginBottom: spacing.md,
  },
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
  outlookBadge: {
    alignSelf: 'flex-start',
    backgroundColor: colors.accentMuted,
    borderRadius: radii.pill,
    paddingHorizontal: spacing.sm,
    paddingVertical: 4,
  },
  outlookBadgeText: { fontSize: 11, fontWeight: '700', color: colors.accent, letterSpacing: 0.4 },
  analyticsRankLine: { fontSize: 13, color: colors.textSecondary },
  analyticsMetricsRow: {
    flexDirection: 'row',
    marginTop: spacing.lg,
    paddingTop: spacing.md,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.border,
  },
  analyticsMetric: { flex: 1, alignItems: 'center' },
  analyticsMetricValue: { fontSize: 18, fontWeight: '700', color: colors.textPrimary },
  analyticsMetricLabel: {
    fontSize: 11,
    fontWeight: '600',
    color: colors.textTertiary,
    marginTop: 2,
    textTransform: 'uppercase',
    letterSpacing: 0.3,
  },
  analyticsMetricNote: { fontSize: 12, color: colors.textSecondary, marginTop: 2 },
  analyticsBars: {
    marginTop: spacing.md,
    paddingTop: spacing.md,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.border,
    gap: spacing.sm,
  },
  percentileBarRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  percentileBarLabel: { fontSize: 12, color: colors.textSecondary, width: 96 },
  percentileBarTrack: {
    flex: 1,
    height: 8,
    borderRadius: 4,
    backgroundColor: colors.background,
    overflow: 'hidden',
  },
  percentileBarFill: { height: '100%', borderRadius: 4 },
  percentileBarValue: { fontSize: 12, fontWeight: '600', color: colors.textSecondary, width: 36, textAlign: 'right' },
  sectionLabel: {
    fontSize: 12,
    fontWeight: '700',
    color: colors.textTertiary,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginTop: spacing.md,
    marginBottom: spacing.sm,
  },
  emptyBench: { fontSize: 13, color: colors.textSecondary },
  card: { flexDirection: 'row', alignItems: 'center', padding: spacing.md, marginBottom: spacing.sm },
  slotBadge: {
    width: 40,
    height: 26,
    borderRadius: radii.sm,
    backgroundColor: colors.badgeBackground,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: spacing.md,
  },
  slotText: { color: colors.badgeText, fontSize: 10, fontWeight: '700' },
  avatar: { marginRight: spacing.sm },
  nameColumn: { flex: 1, marginRight: spacing.sm },
  name: { fontSize: 15, fontWeight: '600', color: colors.textPrimary },
  meta: { fontSize: 12, color: colors.textSecondary, flexShrink: 1 },
  metaRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs, marginTop: 2 },
  injuryPill: {
    backgroundColor: colors.dangerMuted,
    borderRadius: radii.pill,
    paddingHorizontal: spacing.sm,
    paddingVertical: 3,
  },
  injuryText: { fontSize: 11, fontWeight: '700', color: colors.danger },
  // Ruled out (Out/IR/PUP) — a solid pill, because this player is only in
  // the suggested lineup when nothing available could fill the slot.
  injuryPillOut: { backgroundColor: colors.danger },
  injuryTextOut: { color: colors.badgeText },
  valueColumn: { alignItems: 'flex-end', marginLeft: spacing.sm },
  valueNumber: { fontSize: 16, fontWeight: '700', color: colors.accent },
  valueLabel: { fontSize: 9, fontWeight: '700', color: colors.textTertiary, letterSpacing: 0.4 },
  notice: { textAlign: 'center', color: colors.textSecondary, lineHeight: 20 },
  error: { color: colors.danger, textAlign: 'center' },
  });
}
