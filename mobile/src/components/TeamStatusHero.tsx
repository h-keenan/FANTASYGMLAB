import React, { useMemo } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import { useIsRestoring, useQuery } from '@tanstack/react-query';

import CompactModule from './CompactModule';
import { LinkModule } from './ModuleTemplates';
import StatusHeader from './StatusHeader';
import AppText from './AppText';
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
import { lineupModuleParts, roomsModuleParts, standingModuleParts, teamStatusHeroModel } from '../lib/teamStatusModules';
import { buildTodayStatusHeader, type StatusAttentionItem } from '../lib/statusHeader';
import { openInsight } from '../lib/insightNav';
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
  attention = [],
  tradeCount = 0,
}: {
  leagueId: string;
  leagueName: string;
  snapshot: TeamSnapshot | null;
  matchup: MatchupResponse | null;
  rankings: TeamRanking[] | null;
  standingsAvailable: boolean | undefined;
  onNavigate: Navigate;
  /** Player rows for "Needs your attention" (lineup holes + single-player items; lib/statusHeader splitTodayAttention). */
  attention?: StatusAttentionItem[];
  /** Trade ideas the dashboard found (a mini stat on the header). */
  tradeCount?: number;
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
  if (!matchupLine && !lineup && !standing && positions.length === 0 && attention.length === 0) return null;

  const fact = (label: string, value: string, tone: keyof typeof toneColor = 'neutral') => (
    <View style={styles.fact} key={label}>
      <AppText style={styles.factLabel}>{label}</AppText>
      <AppText style={[styles.factValue, { color: toneColor[tone] }]} numberOfLines={1} adjustsFontSizeToFit>
        {value}
      </AppText>
    </View>
  );
  const heroModel = teamStatusHeroModel(matchupLine, standing);
  const heroIsStanding = heroModel != null && !(matchupLine && (matchupLine.winPercent != null || matchupLine.live));
  const showStanding = standing != null && (!heroIsStanding || Boolean(standing.playoffOdds || standing.projectedRecord || standing.playoffStatus));

  // Route names stand in for the web hrefs; StatusHeader hands them back through onOpen.
  const statusModel = buildTodayStatusHeader({
    matchup: matchupLine,
    hero: heroModel,
    lineup,
    standing,
    attention,
    tradeCount,
    hrefs: { matchup: 'Matchup', rankings: 'Teams', trades: 'Trades' },
  });

  return (
    <View style={styles.block}>
      {/* The players-first status header (ring, 3 mini stats, player rows, one action), then the modules that read while collapsed. Mirrors web. */}
      {statusModel ? (
        <StatusHeader
          model={statusModel}
          headerHref={matchupLine ? 'Matchup' : 'Teams'}
          onOpen={(route) => onNavigate(route, { leagueId, leagueName })}
          testID="team-status-main"
        />
      ) : null}

      {lineup ? (
        <LinkModule
          title="Lineup"
          tone={lineup.tone === 'risk' ? 'danger' : lineup.tone === 'positive' ? 'success' : 'accent'}
          parts={lineupModuleParts(lineup)}
          onPress={() => onNavigate('Matchup', { leagueId, leagueName })}
          testID="team-status-lineup"
        />
      ) : null}

      {standing && showStanding ? (
        <CompactModule
          id="today.standing"
          title="Standing"
          tone={standing.tone === 'risk' ? 'danger' : standing.tone === 'positive' ? 'success' : 'accent'}
          parts={standingModuleParts(standing)}
        >
          <View style={styles.facts}>
            {standing.record ? fact('Record', standing.record) : null}
            {standing.place ? fact('Standing', standing.place) : null}
            {standing.playoffOdds ? fact('Playoff odds', standing.playoffOdds, standing.tone) : null}
            {standing.projectedRecord ? fact('Proj. record', standing.projectedRecord) : null}
          </View>
          {standing.playoffOdds && simQuery.data?.weeks_remaining ? (
            <AppText style={styles.muted}>Odds from a rest-of-season simulation: {simQuery.data.weeks_remaining} weeks left.</AppText>
          ) : null}
          {standing.playoffStatus ? <AppText style={styles.secondary}>{standing.playoffStatus}</AppText> : null}
          <Pressable accessibilityRole="link" onPress={() => onNavigate('Teams', { leagueId, leagueName })} style={{ minHeight: 44, justifyContent: 'center' }}>
            <AppText style={styles.link}>Open League Rankings ›</AppText>
          </Pressable>
        </CompactModule>
      ) : null}

      {positions.length > 0 ? (
        <CompactModule id="today.rooms" title="Position rooms" tone={weakest ? 'warning' : 'accent'} parts={roomsModuleParts(positions)}>
          <AppText style={styles.muted}>Position rooms vs the league. Tap a room for the detail ›</AppText>
          <View style={styles.chips}>
            {positions.map((position: TeamStatusPosition) => {
              const color = toneColor[position.tone];
              return (
                <Pressable
                  key={position.position}
                  accessibilityRole="button"
                  accessibilityLabel={`${position.position}: ${position.label}${position.weakest ? ', weakest room' : ''}, open Team Analysis on My Team`}
                  onPress={openInsight(onNavigate, 'position_room', leagueId, leagueName)}
                  style={[styles.chip, position.weakest && { borderColor: color }]}
                >
                  <AppText style={styles.chipPos}>{position.position}</AppText>
                  <AppText style={[styles.chipLabel, { color }]}>{position.label}</AppText>
                </Pressable>
              );
            })}
          </View>
          {weakest ? (
            <Pressable accessibilityRole="link" onPress={() => onNavigate('Trades', { leagueId, leagueName })} style={{ minHeight: 44, justifyContent: 'center' }}>
              <AppText style={styles.link}>Improve {weakest.position} first: see Trade Hub ideas ›</AppText>
            </Pressable>
          ) : null}
        </CompactModule>
      ) : null}
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
    vs: { fontSize: 12.5, fontWeight: '800', letterSpacing: 0.8, color: colors.textTertiary },
    lineupHead: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
    facts: { flexDirection: 'row', gap: spacing.sm },
    fact: { flex: 1, minWidth: 0 },
    factLabel: { fontSize: 12.5, color: colors.textTertiary },
    factValue: { fontSize: 17, fontWeight: '800' },
    muted: { fontSize: 13.5, color: colors.textTertiary },
    secondary: { fontSize: 13.5, color: colors.textSecondary },
    strong: { fontSize: 15.5, fontWeight: '700', color: colors.textPrimary },
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
    chipPos: { fontSize: 13.5, fontWeight: '800', color: colors.textPrimary },
    chipLabel: { fontSize: 12.5, textAlign: 'center' },
    link: { fontSize: 13.5, fontWeight: '700', color: colors.accent },
  });
}
