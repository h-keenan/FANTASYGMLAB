import React, { useMemo } from 'react';
import { StyleSheet, View } from 'react-native';

import AppText from './AppText';
import CompactModule from './CompactModule';
import EmptyState from './EmptyState';
import PressableScale from './PressableScale';
import TeamAvatar from './TeamAvatar';
import { useThemeMode } from '../context/ThemeModeContext';
import type { LeagueTeamRankingsResponse, TeamRanking } from '../lib/api';
import {
  STANDINGS_EMPTY,
  STANDINGS_NOTE,
  sortByStanding,
  standingRecord,
  standingsSummaryParts,
  standingsTitle,
} from '../lib/leagueStandings';
import { formatRank } from '../lib/percentile';
import { spacing, type ThemeColors } from '../theme';

/**
 * League Rankings > Standings (twin of web LeagueRankingsContent's StandingsSection): actual results, separate from Roster
 * Power. One compact module: collapsed it names the leader and where you sit; expanded it lists every team with record,
 * win %, PF/PA and the playoff line. Copy, order and summary come from the lib twin `leagueStandings.ts`.
 */
export default function LeagueStandingsModule({
  data,
  myRosterId,
  avatarIdByRoster,
  onOpenTeam,
}: {
  data: LeagueTeamRankingsResponse;
  myRosterId: string;
  avatarIdByRoster: Record<string, string>;
  onOpenTeam: (team: TeamRanking) => void;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const title = standingsTitle(data.season);
  const ordered = useMemo(() => sortByStanding(data.teams), [data.teams]);

  if (!data.standings_available) {
    return (
      <CompactModule id="league.standings" title={title} parts={[{ key: 'none', text: 'Not available yet', tone: 'muted' }]} testID="league-standings">
        <EmptyState icon="information-circle-outline" title={data.standings_message || STANDINGS_EMPTY} />
      </CompactModule>
    );
  }

  return (
    <CompactModule id="league.standings" title={title} parts={standingsSummaryParts(ordered, myRosterId)} testID="league-standings">
      <AppText style={styles.note}>{`${data.week_label ? `${data.week_label} — ` : ''}${STANDINGS_NOTE}`}</AppText>
      <View>
        {ordered.map((team) => {
          const mine = team.roster_id === myRosterId;
          const detail = [
            `Win% ${team.win_pct_label ?? '—'}`,
            `PF ${team.points_for_label ?? '0.0'}`,
            `PA ${team.points_against_label ?? '0.0'}`,
            team.playoff_status ?? null,
          ]
            .filter(Boolean)
            .join(' · ');
          return (
            <View key={team.roster_id}>
              <PressableScale
                onPress={() => onOpenTeam(team)}
                accessibilityRole="button"
                accessibilityLabel={`${team.team_name || 'Team'} standings, ${standingRecord(team)}`}
                style={[styles.row, mine && styles.rowMine]}
              >
                <AppText style={styles.rank}>{formatRank(team.standing_rank)}</AppText>
                <TeamAvatar avatarId={avatarIdByRoster[team.roster_id]} name={team.team_name} size={32} />
                <View style={styles.main}>
                  <AppText style={styles.name} numberOfLines={1}>
                    {team.team_name || 'Team'}
                    {mine ? ' (You)' : ''}
                  </AppText>
                  <AppText style={styles.detail} numberOfLines={1}>{detail}</AppText>
                </View>
                <AppText style={styles.record}>{team.record_label || '0-0'}</AppText>
              </PressableScale>
              {team.on_playoff_line ? (
                <AppText style={styles.line} accessibilityLabel="Playoff line">Playoff line</AppText>
              ) : null}
            </View>
          );
        })}
      </View>
    </CompactModule>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    note: { fontSize: 13, color: colors.textTertiary, marginBottom: spacing.sm },
    row: { minHeight: 48, flexDirection: 'row', alignItems: 'center', gap: spacing.sm, paddingVertical: spacing.xs },
    rowMine: { backgroundColor: colors.accentMuted, borderRadius: 8, paddingHorizontal: spacing.xs },
    rank: { width: 32, fontSize: 13.5, fontWeight: '800', color: colors.textSecondary },
    main: { flex: 1, minWidth: 0 },
    name: { fontSize: 15, fontWeight: '700', color: colors.textPrimary },
    detail: { fontSize: 12.5, color: colors.textTertiary },
    record: { fontSize: 15, fontWeight: '800', color: colors.textPrimary },
    line: { fontSize: 12.5, fontWeight: '800', color: colors.accent, textTransform: 'uppercase', textAlign: 'center', paddingVertical: 2, letterSpacing: 0.6 },
  });
}
