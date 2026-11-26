import React, { useMemo } from 'react';
import { StyleSheet, View } from 'react-native';
import { useQuery } from '@tanstack/react-query';

import AppText from './AppText';
import EmptyState from './EmptyState';
import { ExpandRow, ExpandRowGroup } from './ExpandRow';
import IconRow from './IconRow';
import PlayerAvatarSlot from './PlayerAvatarSlot';
import SectionHeading from './SectionHeading';
import TeamAvatar from './TeamAvatar';
import TeamNameLink from './TeamNameLink';
import ToneBadge from './ToneBadge';
import { useThemeMode } from '../context/ThemeModeContext';
import { api } from '../lib/api';
import {
  flagText,
  flagTone,
  formatPoints,
  gapLabel,
  gapTone,
  lineupsReasonMessage,
  lineupsSummaryLine,
  setVsBestLine,
  swapLine,
  type CommissionerLineupsResponse,
  type LineupCheckTeam,
  type LineupTone,
} from '../lib/commissionerLineups';
import { queryKeys } from '../lib/queryKeys';
import { spacing, type ThemeColors } from '../theme';

/**
 * Commissioner "Lineup check" (native twin of web-next/src/components/LineupCheck.tsx): every team's set lineup vs its
 * best lineup this week, worst gap first, one ExpandRow per team that opens to the swaps that would fix it. Numbers come
 * from modules/commissioner_lineups.py. A big gap is a prompt to look, never a verdict: warning/muted tones, never red.
 */
function useToneColor(): (tone: LineupTone) => string {
  const { colors } = useThemeMode();
  return (tone) => (tone === 'warning' ? colors.warning : tone === 'success' ? colors.success : tone === 'information' ? colors.accent : colors.textTertiary);
}

function TeamRow({ team, leagueId, leagueName, styles }: { team: LineupCheckTeam; leagueId: string; leagueName: string; styles: ReturnType<typeof createStyles> }) {
  const toneColor = useToneColor();
  return (
    <ExpandRow
      testID={`lineup-team-${team.roster_id}`}
      label={`${team.team_name}, ${setVsBestLine(team)}`}
      // team-tap-exempt: the whole row is one expand toggle; the team sheet opens from the team link inside it
      leading={<TeamAvatar avatarId={team.avatar_url} name={team.team_name} size={32} />}
      title={team.team_name}
      caption={setVsBestLine(team)}
      chips={
        <>
          {team.possible_tanking ? <ToneBadge label="Possible tanking" color={toneColor('warning')} /> : null}
          {team.flags.map((f, i) => (
            <ToneBadge key={`${f.kind}-${i}`} label={flagText(f)} color={toneColor(flagTone(f.kind))} />
          ))}
          {team.locked_count ? <ToneBadge label={`${team.locked_count} locked`} color={toneColor('muted')} /> : null}
        </>
      }
      action={<ToneBadge label={gapLabel(team)} color={toneColor(gapTone(team))} />}
    >
      <TeamNameLink leagueId={leagueId} leagueName={leagueName} rosterId={team.roster_id} name={team.team_name} textStyle={styles.teamLink} />
      {team.swaps.length ? (
        <View style={styles.group}>
          <AppText style={styles.groupTitle}>Swaps that fix it</AppText>
          {team.swaps.map((s, i) => (
            <IconRow key={`${s.slot}-${i}`} icon="arrow">
              {swapLine(s)}
            </IconRow>
          ))}
        </View>
      ) : (
        <AppText style={styles.muted}>
          {team.gap != null && team.gap > 0
            ? 'No swap is available: the players who would help are locked or not on the roster.'
            : 'Nothing to fix: the set lineup matches the best one.'}
        </AppText>
      )}
      {team.starters.length ? (
        <View style={styles.group}>
          <AppText style={styles.groupTitle}>Starters they set</AppText>
          {team.starters.map((s, i) => (
            <View key={`${s.player_id}-${i}`} style={styles.starter}>
              <PlayerAvatarSlot player={{ id: s.player_id, name: s.name ?? 'Unknown player', position: s.position, team: s.team }} tier="row" />
              <AppText style={styles.starterName} numberOfLines={1}>
                <AppText style={styles.muted}>{s.slot ? `${s.slot} ` : ''}</AppText>
                {s.name ?? 'Unknown player'}
              </AppText>
              {s.availability ? <ToneBadge label={s.availability === 'bye' ? 'Bye' : s.availability === 'ir' ? 'IR' : 'Out'} color={toneColor(s.availability === 'bye' ? 'information' : 'warning')} /> : null}
              {s.locked ? <ToneBadge label="Locked" color={toneColor('muted')} /> : null}
              <AppText style={styles.points}>{formatPoints(s.points)}</AppText>
            </View>
          ))}
        </View>
      ) : null}
    </ExpandRow>
  );
}

function LineupCheckView({ data, leagueId, leagueName }: { data: CommissionerLineupsResponse; leagueId: string; leagueName: string }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  if (data.reason) return <EmptyState icon="shield-checkmark-outline" title="Nothing to check yet" subtitle={lineupsReasonMessage(data.reason)} />;
  return (
    <View style={styles.stack}>
      <AppText style={styles.body}>{lineupsSummaryLine(data)}</AppText>
      <ExpandRowGroup accent={colors.warning} testID="lineup-teams">
        {data.teams.map((t) => (
          <TeamRow key={t.roster_id} team={t} leagueId={leagueId} leagueName={leagueName} styles={styles} />
        ))}
      </ExpandRowGroup>
      {data.limits?.length ? (
        <View style={styles.group}>
          <AppText style={styles.groupTitle}>What this can and can&rsquo;t tell you</AppText>
          {data.limits.map((limit) => (
            <IconRow key={limit} icon="info" color={colors.textTertiary}>
              {limit}
            </IconRow>
          ))}
        </View>
      ) : null}
    </View>
  );
}

/** Self-loading section for the Commissioner screen. Renders nothing while loading, on error, or for a Free user. */
export default function LineupCheck({ leagueId, leagueName, lens }: { leagueId: string; leagueName: string; lens: string }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const query = useQuery({
    queryKey: queryKeys.commissionerLineups(leagueId, lens),
    queryFn: () => api.getCommissionerLineups(leagueId, lens),
    staleTime: 2 * 60 * 1000,
  });
  const data = query.data;
  if (!data || data.is_premium === false) return null;
  return (
    <View style={styles.stack}>
      <SectionHeading title="Lineup check" caption="Each team's set lineup vs its best lineup this week. A big gap is a prompt to look, not a verdict." />
      <LineupCheckView data={data} leagueId={leagueId} leagueName={leagueName} />
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    stack: { gap: spacing.md, marginTop: spacing.lg },
    body: { fontSize: 15.5, color: colors.textSecondary },
    teamLink: { fontSize: 14, fontWeight: '800', color: colors.textPrimary },
    muted: { fontSize: 13.5, color: colors.textTertiary },
    group: { gap: spacing.xs },
    groupTitle: { fontSize: 12.5, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.8, color: colors.textTertiary },
    starter: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
    starterName: { flex: 1, minWidth: 0, fontSize: 14, color: colors.textPrimary },
    points: { fontSize: 14, fontWeight: '700', color: colors.textSecondary },
  });
}
