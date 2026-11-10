import React, { useMemo } from 'react';
import { StyleSheet, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useIsRestoring, useQuery } from '@tanstack/react-query';

import AnimatedCard from './AnimatedCard';
import AppText from './AppText';
import ToneBadge from './ToneBadge';
import IconCircle from './IconCircle';
import TeamAvatar from './TeamAvatar';
import { api } from '../lib/api';
import { seasonOddsLine } from '../lib/gamesPresentation';
import { queryKeys } from '../lib/queryKeys';
import { useThemeMode } from '../context/ThemeModeContext';
import { spacing, type ThemeColors } from '../theme';

function scoringLabel(scoringSettings: Record<string, unknown> | undefined): string {
  const rec = Number(scoringSettings?.rec ?? 0);
  if (rec >= 1) return 'PPR';
  if (rec > 0) return 'Half PPR';
  return 'Standard';
}

/**
 * League context on the one landing screen (moved from the retired League
 * Overview): season / week / team count / scoring line, a "your team" strip
 * that opens the roster, and a simulated-playoff-odds strip that opens
 * Playoff Odds. Self-fetching through React Query (cache-first), each part
 * hides itself when its data is not available.
 */
export default function LeagueStandingStrips({
  leagueId,
  onNavigate,
}: {
  leagueId: string;
  onNavigate: (name: string, params?: object) => void;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const isRestoring = useIsRestoring();

  const leagueQuery = useQuery({
    queryKey: queryKeys.leagueInfo(leagueId),
    queryFn: () => api.getLeague(leagueId),
    enabled: !isRestoring,
  });
  const rosterQuery = useQuery({
    queryKey: queryKeys.myRoster(leagueId),
    queryFn: () => api.getMyRoster(leagueId),
    enabled: !isRestoring,
  });
  const profilesQuery = useQuery({
    queryKey: queryKeys.teamProfiles(leagueId),
    queryFn: () => api.getLeagueTeamProfiles(leagueId),
    enabled: !isRestoring,
  });
  const oddsQuery = useQuery({
    queryKey: queryKeys.seasonSim(leagueId),
    queryFn: () => api.getGamesSeasonSim(leagueId),
    enabled: !isRestoring,
  });

  const league = leagueQuery.data?.league;
  const summary = league
    ? (() => {
        const settings = (league.settings as Record<string, unknown>) ?? {};
        return `${String(league.season ?? '—')} · Week ${settings.leg ? String(settings.leg) : '—'} · ${String(
          league.total_rosters ?? '—',
        )} teams · ${scoringLabel(league.scoring_settings as Record<string, unknown>)}`;
      })()
    : null;

  const roster = rosterQuery.data?.roster as { roster_id?: unknown; players?: unknown } | null | undefined;
  const rosterId = roster ? String(roster.roster_id ?? '') : '';
  const profile = rosterId ? profilesQuery.data?.profiles?.[rosterId] : undefined;
  const playerIds = roster && Array.isArray(roster.players) ? roster.players.map(String) : [];
  const myTeam = roster && profilesQuery.data ? { teamName: profile?.team_name || 'Your team', avatarId: profile?.avatar_id || '' } : null;

  const odds = oddsQuery.data;
  const myOdds = odds && !odds.reason ? odds.my_team : null;
  const oddsLine = seasonOddsLine(odds);

  const leagueName = (league?.name as string | undefined) ?? '';

  return (
    <>
      {summary ? (
        <View style={styles.contextRow}>
          <Ionicons name="calendar-outline" size={13} color={colors.textTertiary} />
          <AppText style={styles.contextText}>{summary}</AppText>
        </View>
      ) : null}

      {myTeam ? (
        <AnimatedCard
          style={styles.stripCard}
          onPress={() =>
            onNavigate('TeamRoster', {
              ownerName: myTeam.teamName,
              playerIds,
              leagueId,
              leagueName,
              rosterId,
            })
          }
        >
          <TeamAvatar avatarId={myTeam.avatarId} size={36} />
          <View style={styles.stripTextGroup}>
            <View style={styles.stripNameRow}>
              <AppText style={styles.stripName} numberOfLines={1}>
                {myTeam.teamName}
              </AppText>
              <ToneBadge label="You" color={colors.accent} textColor={colors.onAccent} solid />
            </View>
          </View>
          <AppText style={styles.stripValue}>{playerIds.length}</AppText>
          <AppText style={styles.stripValueLabel}>PLAYERS</AppText>
        </AnimatedCard>
      ) : null}

      {myOdds && oddsLine ? (
        <AnimatedCard style={styles.stripCard} onPress={() => onNavigate('Games', { leagueId, leagueName })}>
          <IconCircle name="podium-outline" color={colors.violet} size={36} />
          <View style={styles.stripTextGroup}>
            <AppText style={styles.stripTextGroup2}>{oddsLine.headline}</AppText>
            {oddsLine.caption ? <AppText style={styles.oddsCaption}>{oddsLine.caption}</AppText> : null}
          </View>
          <Ionicons name="chevron-forward" size={18} color={colors.textTertiary} />
        </AnimatedCard>
      ) : null}
    </>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    contextRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
    contextText: { fontSize: 13.5, fontWeight: '500', color: colors.textSecondary, letterSpacing: 0.2 },
    stripCard: { flexDirection: 'row', alignItems: 'center', paddingVertical: spacing.md, gap: spacing.sm },
    stripTextGroup: { flex: 1 },
    stripNameRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs },
    stripName: { fontSize: 16.5, fontWeight: '600', color: colors.textPrimary, flexShrink: 1 },
    stripValue: { fontSize: 17, fontWeight: '700', color: colors.textPrimary },
    stripValueLabel: { fontSize: 12, fontWeight: '700', color: colors.textTertiary, marginLeft: 4 },
    oddsCaption: { fontSize: 12.5, color: colors.textTertiary, marginTop: 2 },
    stripTextGroup2: { flex: 1, fontSize: 15.5, fontWeight: '600', color: colors.textPrimary },
  });
}
