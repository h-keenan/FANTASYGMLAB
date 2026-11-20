import React, { useMemo, useState } from 'react';
import { AppState, StyleSheet, View } from 'react-native';
import { useIsFocused } from '@react-navigation/native';
import { keepPreviousData, useIsRestoring, useQuery } from '@tanstack/react-query';

import AppText from './AppText';
import CompactModule from './CompactModule';
import FreshnessLabel from './FreshnessLabel';
import { Collapse } from './Presence';
import { ProgressFill } from './Motion';
import PressableScale from './PressableScale';
import TeamNameLink from './TeamNameLink';
import { WeekSelect } from './PageControlRow';
import { useThemeMode } from '../context/ThemeModeContext';
import { api, type LeagueMatchupsResponse } from '../lib/api';
import {
  defaultMatchupWeek,
  formatMatchupPoints,
  formatMatchupProjected,
  LEAGUE_MATCHUPS_TITLE,
  leagueMatchupsHidden,
  leagueMatchupsSummaryParts,
  leagueMatchupWeeks,
  matchupStateLabel,
  pairAriaLabel,
  pairTones,
  sideSubline,
  winPercent,
  type LeagueMatchupPairView,
  type LeagueMatchupSideView,
  type LeagueMatchupTone,
} from '../lib/leagueMatchups';
import { nextPollDelayMs } from '../lib/liveScores';
import { queryKeys } from '../lib/queryKeys';
import { radii, spacing, type ThemeColors } from '../theme';

/**
 * The League page's Matchups section (twin of web LeagueMatchupsSection): every pair of a week as one compact card, both teams
 * with avatars and a VS chip, live points big with the projected total under them, a win-chance bar per side. Numbers come
 * from the same server computation as the Matchup screen (GET .../matchups) and refetch on the live-poll rules (lib/liveScores)
 * while games are on. A team name opens the shared team sheet (TeamNameLink); "Details" expands handles and projections. The
 * Matchup screen only shows YOUR pair, so only your card offers "Open my matchup". Leader green, trailing muted, never red.
 */

function toneColor(colors: ThemeColors, tone: LeagueMatchupTone): string {
  return tone === 'leader' ? colors.success : tone === 'trailing' ? colors.textTertiary : colors.textPrimary;
}

function SideHead({ side, leagueId, leagueName, end, colors }: { side: LeagueMatchupSideView; leagueId: string; leagueName: string; end: boolean; colors: ThemeColors }) {
  return (
    <View style={[headStyles.col, end && headStyles.colEnd]}>
      <TeamNameLink
        leagueId={leagueId}
        leagueName={leagueName}
        rosterId={side.roster_id}
        name={side.team_name}
        avatarId={side.avatar_url}
        ownerName={side.owner_name}
        showAvatar
        avatarSize={28}
        alignEnd={end}
        textStyle={{ fontSize: 14, fontWeight: '700', color: colors.textPrimary, textAlign: end ? 'right' : 'left' }}
        style={end ? { flexDirection: 'row-reverse' } : undefined}
      />
      <AppText style={{ fontSize: 12, color: colors.textTertiary }} numberOfLines={1}>
        {sideSubline(side)}
      </AppText>
    </View>
  );
}

const headStyles = StyleSheet.create({
  col: { flex: 1, minWidth: 0, alignItems: 'flex-start', gap: 2 },
  colEnd: { alignItems: 'flex-end' },
});

function Score({ side, tone, end, colors }: { side: LeagueMatchupSideView; tone: LeagueMatchupTone; end: boolean; colors: ThemeColors }) {
  const proj = formatMatchupProjected(side.projected_total);
  return (
    <View style={{ flex: 1, alignItems: end ? 'flex-end' : 'flex-start' }}>
      <AppText style={{ fontSize: 24, fontWeight: '800', color: toneColor(colors, tone), fontVariant: ['tabular-nums'] }}>
        {formatMatchupPoints(side.points)}
      </AppText>
      {proj ? <AppText style={{ fontSize: 12, color: colors.textTertiary, fontVariant: ['tabular-nums'] }}>{proj}</AppText> : null}
    </View>
  );
}

function MatchupCard({ pair, leagueId, leagueName, colors, styles, onOpenMyMatchup }: { pair: LeagueMatchupPairView; leagueId: string; leagueName: string; colors: ThemeColors; styles: ReturnType<typeof createStyles>; onOpenMyMatchup?: () => void }) {
  const [open, setOpen] = useState(false);
  const [a, b] = pair.sides;
  const [toneA, toneB] = pairTones(pair);
  const modeled = winPercent(a.win_probability) !== null;
  const mine = a.is_mine || b.is_mine;
  return (
    <View style={[styles.card, mine && styles.cardMine]} accessible={false} accessibilityLabel={pairAriaLabel(pair)} testID="league-matchup-card">
      <View style={styles.row}>
        <SideHead side={a} leagueId={leagueId} leagueName={leagueName} end={false} colors={colors} />
        <View style={styles.vs}>
          <AppText style={styles.vsText}>VS</AppText>
        </View>
        <SideHead side={b} leagueId={leagueId} leagueName={leagueName} end colors={colors} />
      </View>
      <View style={styles.row}>
        <Score side={a} tone={toneA} end={false} colors={colors} />
        <Score side={b} tone={toneB} end colors={colors} />
      </View>
      <View style={styles.bars} accessibilityRole="progressbar" accessibilityLabel={modeled ? `${winPercent(a.win_probability)} percent to ${winPercent(b.win_probability)} percent` : 'Win chance not modeled yet'}>
        {([[toneA, winPercent(a.win_probability)], [toneB, winPercent(b.win_probability)]] as const).map(([tone, pct], i) => (
          <View key={i} style={styles.track}>
            <ProgressFill percent={modeled ? pct : 0} color={toneColor(colors, tone)} />
          </View>
        ))}
      </View>
      <View style={styles.pctRow}>
        <AppText style={[styles.pct, { color: toneColor(colors, toneA) }]}>{modeled ? `${winPercent(a.win_probability)}%` : '—'}</AppText>
        <AppText style={[styles.pct, { color: colors.textTertiary }]}>{matchupStateLabel(pair.game_state)}</AppText>
        <AppText style={[styles.pct, { color: toneColor(colors, toneB) }]}>{modeled ? `${winPercent(b.win_probability)}%` : '—'}</AppText>
      </View>
      <PressableScale accessibilityRole="button" accessibilityState={{ expanded: open }} accessibilityLabel="Matchup details" onPress={() => setOpen((v) => !v)} style={styles.details}>
        <AppText style={styles.detailsLabel}>Details</AppText>
        <AppText style={styles.detailsAction}>{open ? 'Hide' : 'Show'}</AppText>
      </PressableScale>
      <Collapse open={open}>
        <View style={{ gap: spacing.xs }}>
          <View style={styles.row}>
            {[a, b].map((s, i) => (
              <View key={s.roster_id} style={{ flex: 1, alignItems: i === 1 ? 'flex-end' : 'flex-start' }}>
                <AppText style={styles.handle} numberOfLines={1}>{s.owner_name ? `@${s.owner_name}` : 'Manager'}</AppText>
                <AppText style={styles.muted}>{formatMatchupProjected(s.projected_total) ?? 'No projection yet'}</AppText>
              </View>
            ))}
          </View>
          {mine && onOpenMyMatchup ? (
            <PressableScale accessibilityRole="link" accessibilityLabel="Open my matchup" onPress={onOpenMyMatchup} style={styles.openMine}>
              <AppText style={styles.detailsAction}>Open my matchup</AppText>
            </PressableScale>
          ) : null}
        </View>
      </Collapse>
    </View>
  );
}

export default function LeagueMatchupsSection({
  leagueId,
  leagueName,
  onOpenMyMatchup,
}: {
  leagueId: string;
  leagueName: string;
  onOpenMyMatchup?: () => void;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const isRestoring = useIsRestoring();
  const isFocused = useIsFocused();
  const [week, setWeek] = useState<number | null>(null);
  const query = useQuery<LeagueMatchupsResponse>({
    queryKey: queryKeys.leagueMatchups(leagueId, week),
    queryFn: () => api.getLeagueMatchups(leagueId, week),
    enabled: !isRestoring,
    placeholderData: keepPreviousData,
    staleTime: (q) => (q.state.data?.live ? 0 : 30_000),
    refetchInterval: (q) =>
      q.state.data?.live === true && isFocused && AppState.currentState === 'active' ? nextPollDelayMs(q.state.data.poll_after_seconds, 0) : false,
    refetchIntervalInBackground: false,
  });
  const data = query.data;
  if (leagueMatchupsHidden(data?.reason)) return null;
  const shownWeek = data?.week ?? defaultMatchupWeek(data?.current_week) ?? null;
  const pairs = data?.matchups ?? [];
  const parts = data
    ? leagueMatchupsSummaryParts(shownWeek, pairs)
    : query.isError
      ? [{ key: 'error', text: 'Could not load', tone: 'muted' as const }]
      : [];
  const weeks = leagueMatchupWeeks(data?.max_week ?? 0);
  return (
    <CompactModule id="league.matchups" title={LEAGUE_MATCHUPS_TITLE} parts={parts} loading={!data && !query.isError} defaultOpen testID="league-matchups">
      {weeks.length > 1 && shownWeek ? (
        <View style={styles.select}>
          <WeekSelect weeks={weeks} value={shownWeek} onChange={setWeek} />
        </View>
      ) : null}
      {pairs.length === 0 && data ? (
        <AppText style={styles.muted}>No matchups for this week yet.</AppText>
      ) : (
        <View style={{ gap: spacing.sm, opacity: query.isPlaceholderData ? 0.6 : 1 }}>
          {pairs.map((pair) => (
            <MatchupCard key={String(pair.matchup_id)} pair={pair} leagueId={leagueId} leagueName={leagueName} colors={colors} styles={styles} onOpenMyMatchup={onOpenMyMatchup} />
          ))}
        </View>
      )}
      <FreshnessLabel datasets={[]} report={null} leagueAsOf={data?.sleeper_data_as_of} />
    </CompactModule>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    select: { minHeight: 44, marginBottom: spacing.sm },
    card: { borderRadius: radii.md, borderWidth: StyleSheet.hairlineWidth, borderColor: colors.border, backgroundColor: colors.surface, padding: spacing.md, gap: spacing.sm },
    cardMine: { borderColor: colors.accent },
    row: { flexDirection: 'row', alignItems: 'flex-start', gap: spacing.sm },
    vs: { marginTop: 4, paddingHorizontal: 8, paddingVertical: 2, borderRadius: radii.pill, backgroundColor: colors.border },
    vsText: { fontSize: 12, fontWeight: '800', color: colors.textTertiary, letterSpacing: 0.6 },
    bars: { flexDirection: 'row', gap: spacing.sm },
    track: { flex: 1, height: 6, borderRadius: radii.pill, overflow: 'hidden', backgroundColor: colors.border },
    pctRow: { flexDirection: 'row', justifyContent: 'space-between' },
    pct: { fontSize: 12, fontWeight: '800', fontVariant: ['tabular-nums'] },
    details: { minHeight: 44, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.border },
    detailsLabel: { fontSize: 12, fontWeight: '700', color: colors.textTertiary },
    detailsAction: { fontSize: 12, fontWeight: '700', color: colors.accent },
    handle: { fontSize: 12, fontWeight: '700', color: colors.textSecondary },
    muted: { fontSize: 12, color: colors.textTertiary },
    openMine: { minHeight: 44, justifyContent: 'center' },
  });
}
