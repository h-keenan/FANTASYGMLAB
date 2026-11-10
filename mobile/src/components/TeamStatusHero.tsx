import React, { useMemo } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useIsRestoring, useQuery } from '@tanstack/react-query';

import AccentCard from './AccentCard';
import AppText from './AppText';
import SectionHeading from './SectionHeading';
import TeamAvatar from './TeamAvatar';
import ToneBadge from './ToneBadge';
import { useThemeMode } from '../context/ThemeModeContext';
import { api, type MatchupResponse, type TeamRanking, type TeamSnapshot } from '../lib/api';
import { queryKeys } from '../lib/queryKeys';
import {
  buildTeamStatusLineup,
  buildTeamStatusMatchup,
  buildTeamStatusOdds,
  buildTeamStatusPositions,
  buildTeamStatusStanding,
  type TeamStatusPosition,
} from '../lib/teamStatus';
import { radii, spacing, type ThemeColors } from '../theme';

type Navigate = (name: string, params?: object) => void;

/**
 * "Your team right now": this week's matchup, lineup health, season standing and
 * position-room strength in one card, each row opening the screen that owns the
 * detail. Built from responses the Dashboard already loads
 * (lib/teamStatus.ts, shared with web); a row with no real data is hidden,
 * never zero-filled. Mirrors web TeamStatusHero.
 */
export default function TeamStatusHero({
  leagueId,
  leagueName,
  snapshot,
  matchup,
  rankings,
  standingsAvailable,
  onNavigate,
}: {
  leagueId: string;
  leagueName: string;
  snapshot: TeamSnapshot | null;
  matchup: MatchupResponse | null;
  rankings: TeamRanking[] | null;
  standingsAvailable: boolean | undefined;
  onNavigate: Navigate;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const isRestoring = useIsRestoring();
  const needsQuery = useQuery({
    queryKey: queryKeys.myTeamNeeds(leagueId),
    queryFn: () => api.getLeagueMyTeamNeeds(leagueId),
    enabled: !isRestoring,
  });
  const simQuery = useQuery({
    queryKey: queryKeys.seasonSim(leagueId),
    queryFn: () => api.getGamesSeasonSim(leagueId),
    enabled: !isRestoring,
  });
  const toneColor = {
    positive: colors.successBright,
    risk: colors.danger,
    warning: colors.warning,
    neutral: colors.textPrimary,
  } as const;

  const matchupLine = buildTeamStatusMatchup(matchup);
  const lineup = buildTeamStatusLineup(matchup, snapshot?.injured_starters);
  const standing = buildTeamStatusStanding({
    snapshot,
    rankings,
    standingsAvailable,
    myRosterId: matchup?.my_team?.roster_id,
    odds: buildTeamStatusOdds(simQuery.data),
  });
  const positions = buildTeamStatusPositions(needsQuery.data?.ok ? needsQuery.data : null);
  const weakest = positions.find((row) => row.weakest);
  if (!matchupLine && !lineup && !standing && positions.length === 0) return null;

  const fact = (label: string, value: string, tone: keyof typeof toneColor = 'neutral') => (
    <View style={styles.fact} key={label}>
      <AppText style={styles.factLabel}>{label}</AppText>
      <AppText style={[styles.factValue, { color: toneColor[tone] }]} numberOfLines={1} adjustsFontSizeToFit>
        {value}
      </AppText>
    </View>
  );
  const row = (label: string, to: string, children: React.ReactNode, first = false) => (
    <Pressable
      accessibilityRole="link"
      accessibilityLabel={label}
      onPress={() => onNavigate(to, { leagueId, leagueName })}
      style={[styles.row, !first && styles.rowDivider]}
    >
      <View style={styles.rowBody}>{children}</View>
      <Ionicons name="chevron-forward" size={16} color={colors.accent} />
    </Pressable>
  );
  const lineupColor = lineup?.tone === 'risk' ? colors.danger : lineup?.tone === 'positive' ? colors.successBright : colors.textTertiary;
  let first = true;
  const takeFirst = () => {
    const was = first;
    first = false;
    return was;
  };

  return (
    <View style={styles.block}>
      <SectionHeading title="Your team right now" />
      <AccentCard accent={colors.accent} compact glow>
        {matchupLine
          ? row(
              "This week's matchup, open Matchup",
              'Matchup',
              <>
                <View style={styles.matchupHead}>
                  <TeamAvatar avatarId={matchupLine.myAvatar} name={matchupLine.myName} size={32} />
                  <AppText style={styles.vs}>VS</AppText>
                  <TeamAvatar avatarId={matchupLine.opponentAvatar} name={matchupLine.opponentName} size={32} />
                  <View style={styles.flex}>
                    <AppText style={styles.muted}>
                      {matchupLine.week != null ? `Week ${matchupLine.week} matchup` : "This week's matchup"}
                      {matchupLine.stateLabel ? ` · ${matchupLine.stateLabel}` : ''}
                    </AppText>
                    <AppText style={styles.strong} numberOfLines={1}>vs {matchupLine.opponentName}</AppText>
                  </View>
                </View>
                <View style={styles.facts}>
                  {matchupLine.winPercent != null
                    ? fact('Your win chance', `${matchupLine.winPercent}%`, matchupLine.winPercent >= 55 ? 'positive' : matchupLine.winPercent <= 45 ? 'risk' : 'neutral')
                    : null}
                  {matchupLine.myProjected != null && matchupLine.opponentProjected != null
                    ? fact('Projected points (you - them)', `${matchupLine.myProjected.toFixed(1)} - ${matchupLine.opponentProjected.toFixed(1)}`)
                    : null}
                  {matchupLine.live
                    ? fact('Score so far (you - them)', `${matchupLine.live.mine.toFixed(1)} - ${matchupLine.live.opponent.toFixed(1)}`)
                    : null}
                </View>
              </>,
              takeFirst(),
            )
          : null}

        {lineup
          ? row(
              'Lineup health, open Matchup',
              'Matchup',
              <>
                <View style={styles.lineupHead}>
                  <ToneBadge label="Lineup" color={lineupColor} />
                  <AppText style={[styles.strong, styles.flex]}>{lineup.headline}</AppText>
                </View>
                {lineup.detail ? <AppText style={styles.secondary}>{lineup.detail}</AppText> : null}
              </>,
              takeFirst(),
            )
          : null}

        {standing
          ? row(
              'Season standing, open League Rankings',
              'Teams',
              <>
                <View style={styles.facts}>
                  {standing.record ? fact('Record', standing.record) : null}
                  {standing.place ? fact('Standing', standing.place) : null}
                  {standing.playoffOdds ? fact('Playoff odds', standing.playoffOdds, standing.tone) : null}
                  {standing.projectedRecord ? fact('Proj. record', standing.projectedRecord) : null}
                </View>
                {standing.playoffOdds && simQuery.data?.weeks_remaining ? (
                  <AppText style={styles.muted}>
                    Odds from a rest-of-season simulation: {simQuery.data.weeks_remaining} weeks left.
                  </AppText>
                ) : null}
                {standing.playoffStatus ? <AppText style={styles.secondary}>{standing.playoffStatus}</AppText> : null}
              </>,
              takeFirst(),
            )
          : null}

        {positions.length > 0 ? (
          <View style={[styles.positions, !first && styles.rowDivider]}>
            <AppText style={styles.muted}>Position rooms vs the league</AppText>
            <View style={styles.chips}>
              {positions.map((position: TeamStatusPosition) => {
                const color = toneColor[position.tone];
                return (
                  <View
                    key={position.position}
                    accessibilityLabel={`${position.position}: ${position.label}${position.weakest ? ', weakest room' : ''}`}
                    style={[styles.chip, position.weakest && { borderColor: color }]}
                  >
                    <AppText style={styles.chipPos}>{position.position}</AppText>
                    <AppText style={[styles.chipLabel, { color }]}>{position.label}</AppText>
                  </View>
                );
              })}
            </View>
            {weakest ? (
              <Pressable accessibilityRole="link" onPress={() => onNavigate('Trades', { leagueId, leagueName })}>
                <AppText style={styles.link}>Improve {weakest.position} first: see Trade Hub ideas ›</AppText>
              </Pressable>
            ) : null}
          </View>
        ) : null}
      </AccentCard>
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    block: { gap: spacing.md },
    flex: { flex: 1, minWidth: 0 },
    row: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, minHeight: 44, paddingVertical: spacing.sm },
    rowDivider: { borderTopWidth: 1, borderTopColor: colors.border },
    rowBody: { flex: 1, minWidth: 0, gap: spacing.xs },
    matchupHead: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
    vs: { fontSize: 11, fontWeight: '800', letterSpacing: 0.8, color: colors.textTertiary },
    lineupHead: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
    facts: { flexDirection: 'row', gap: spacing.sm },
    fact: { flex: 1, minWidth: 0 },
    factLabel: { fontSize: 11, color: colors.textTertiary },
    factValue: { fontSize: 16, fontWeight: '800' },
    muted: { fontSize: 12, color: colors.textTertiary },
    secondary: { fontSize: 12, color: colors.textSecondary },
    strong: { fontSize: 14, fontWeight: '700', color: colors.textPrimary },
    positions: { gap: spacing.sm, paddingTop: spacing.sm },
    chips: { flexDirection: 'row', gap: spacing.sm },
    chip: {
      flex: 1,
      minWidth: 0,
      alignItems: 'center',
      paddingVertical: spacing.xs,
      borderRadius: radii.md,
      borderWidth: 1,
      borderColor: colors.border,
      backgroundColor: colors.surface,
    },
    chipPos: { fontSize: 12, fontWeight: '800', color: colors.textPrimary },
    chipLabel: { fontSize: 11, textAlign: 'center' },
    link: { fontSize: 12, fontWeight: '700', color: colors.accent },
  });
}
