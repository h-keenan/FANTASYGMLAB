import React, { useMemo, useState } from 'react';
import { ScrollView, StyleSheet, TouchableOpacity, View } from 'react-native';
import { keepPreviousData, useIsRestoring, useQuery } from '@tanstack/react-query';

import AccentCard from './AccentCard';
import AppText from './AppText';
import EmptyState from './EmptyState';
import ErrorState from './ErrorState';
import PositionBadge from './PositionBadge';
import PremiumLock from './PremiumLock';
import SegmentedTabBar from './SegmentedTabBar';
import SkeletonBlock from './SkeletonBlock';
import { api, type RoundupResponse, type RoundupSwap, type WeeklyRoundup } from '../lib/api';
import { accentTokenColor } from '../lib/destinationAccent';
import { toUserErrorMessage } from '../lib/errorMessages';
import { queryKeys } from '../lib/queryKeys';
import {
  PREDICTABILITY_LABEL,
  formatPoints,
  predictabilityToken,
  regretBarPercent,
  roundupReasonMessage,
  roundupWeeks,
  swapLine,
} from '../lib/roundupPresentation';
import { useThemeMode } from '../context/ThemeModeContext';
import { radii, spacing, type ThemeColors } from '../theme';

/**
 * League Recaps > Roundup: your lineup against the best one you could have
 * set for a completed week (GET .../roundup, modules/weekly_roundup.py).
 * Starters vs optimal, each missed swap tagged foreseeable / coin flip /
 * unforeseeable, a takeaway and the season bench-regret tally. Free gets the
 * headline numbers plus the biggest swap; the server withholds the rest.
 * Mirrors web-next's LeagueRoundupTab.
 */
export default function RoundupPanel({
  leagueId,
  leagueName,
  initialWeek,
  bottomInset,
}: {
  leagueId: string;
  leagueName: string;
  initialWeek?: number;
  bottomInset: number;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const isRestoring = useIsRestoring();
  const [week, setWeek] = useState<number | undefined>(initialWeek);
  const query = useQuery({
    queryKey: queryKeys.roundup(leagueId, week),
    queryFn: () => api.getLeagueRoundup(leagueId, week != null ? { week } : undefined),
    enabled: !isRestoring,
    placeholderData: keepPreviousData,
  });
  const data = query.data;

  let body: React.ReactNode;
  if (query.isError && !data) {
    body = (
      <ErrorState
        title="Couldn't load your roundup"
        message={toUserErrorMessage(query.error, 'Failed to load your roundup.')}
        onRetry={() => void query.refetch()}
      />
    );
  } else if (!data) {
    body = (
      <View style={styles.stack}>
        <SkeletonBlock width="50%" height={24} />
        <SkeletonBlock height={120} radius={radii.md} />
        <SkeletonBlock height={150} radius={radii.md} />
      </View>
    );
  } else if (!data.roundup) {
    const message = roundupReasonMessage(data.reason);
    body = <EmptyState icon="stats-chart-outline" title={message.title} subtitle={message.subtitle} />;
  } else {
    body = (
      <RoundupBody
        data={data}
        roundup={data.roundup}
        leagueName={leagueName}
        selectedWeek={data.week}
        onSelectWeek={setWeek}
        dim={query.isFetching}
      />
    );
  }

  return (
    <ScrollView contentContainerStyle={[styles.content, { paddingBottom: bottomInset }]}>{body}</ScrollView>
  );
}

function RoundupBody({
  data,
  roundup,
  leagueName,
  selectedWeek,
  onSelectWeek,
  dim,
}: {
  data: RoundupResponse;
  roundup: WeeklyRoundup;
  leagueName: string;
  selectedWeek: number;
  onSelectWeek: (week: number) => void;
  dim: boolean;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const weeks = roundupWeeks(data.max_completed_week);
  const benchTone = roundup.left_on_bench >= 3 ? colors.danger : colors.success;
  const hidden = Math.max(0, (roundup.swaps_total ?? roundup.swaps.length) - roundup.swaps.length);

  return (
    <View style={[styles.stack, dim && { opacity: 0.6 }]}>
      {weeks.length > 1 ? (
        <SegmentedTabBar
          scrollable
          options={weeks.map((w) => ({ key: String(w), label: `Wk ${w}` }))}
          active={String(selectedWeek)}
          onChange={(key) => onSelectWeek(Number(key))}
        />
      ) : null}

      <AccentCard accent={colors.accent}>
        <AppText style={styles.kicker}>WEEKLY ROUNDUP</AppText>
        <AppText style={styles.heading}>Week {roundup.week}</AppText>
        <View style={styles.statRow}>
          <Stat label="You scored" value={formatPoints(roundup.actual_points)} styles={styles} />
          <Stat label="Best possible" value={formatPoints(roundup.optimal_points)} styles={styles} />
          <Stat label="Left on bench" value={formatPoints(roundup.left_on_bench)} color={benchTone} styles={styles} />
        </View>
        <AppText style={styles.body}>{roundup.takeaway}</AppText>
      </AccentCard>

      {roundup.swaps.length === 0 ? (
        <AppText style={styles.muted}>No swaps would have gained meaningful points this week.</AppText>
      ) : (
        <View style={styles.stack}>
          <AppText style={styles.sectionTitle}>{data.is_premium ? 'Missed swaps' : 'Biggest miss'}</AppText>
          {roundup.swaps.map((swap) => (
            <SwapCard key={`${swap.slot}-${swap.started.player_id}-${swap.benched.player_id}`} swap={swap} />
          ))}
          {hidden > 0 ? (
            <AppText style={styles.muted}>
              {hidden} more missed swap{hidden === 1 ? '' : 's'} with Pro.
            </AppText>
          ) : null}
        </View>
      )}

      {data.is_premium && roundup.lineup.length > 0 ? (
        <View style={styles.stack}>
          <AppText style={styles.sectionTitle}>Your lineup vs the best one</AppText>
          <View style={styles.lineupCard}>
            {roundup.lineup.map((row, index) => {
              const changed = row.actual.player_id !== row.optimal.player_id;
              return (
                <View key={`${row.slot}-${index}`} style={styles.lineupRow}>
                  <View style={styles.slotCell}>
                    <PositionBadge position={row.slot} />
                  </View>
                  <AppText style={[styles.lineupName, changed && styles.muted]} numberOfLines={1}>
                    {row.actual.player_id ? `${row.actual.name} ${formatPoints(row.actual.points)}` : 'Empty'}
                  </AppText>
                  <AppText style={[styles.lineupName, changed && { color: colors.success, fontWeight: '700' }]} numberOfLines={1}>
                    {row.optimal.player_id ? `${row.optimal.name} ${formatPoints(row.optimal.points)}` : 'Empty'}
                  </AppText>
                </View>
              );
            })}
          </View>
        </View>
      ) : null}

      {data.is_premium && data.season ? (
        <View style={styles.stack}>
          <AppText style={styles.sectionTitle}>Bench regret, season to date</AppText>
          <AccentCard accent={colors.violet}>
            <AppText style={styles.body}>{data.season.summary}</AppText>
            {(() => {
              const worst = Math.max(0, ...data.season.weeks.map((w) => w.left_on_bench));
              return data.season.weeks.map((w) => (
                <View key={w.week} style={styles.regretRow}>
                  <AppText style={styles.regretWeek}>Wk {w.week}</AppText>
                  <View style={styles.regretTrack}>
                    <View style={[styles.regretFill, { width: `${regretBarPercent(w.left_on_bench, worst)}%`, backgroundColor: colors.violet }]} />
                  </View>
                  <AppText style={styles.regretValue}>{formatPoints(w.left_on_bench)}</AppText>
                </View>
              ));
            })()}
          </AccentCard>
        </View>
      ) : null}

      {!data.is_premium && data.upsell ? (
        <PremiumLock
          title={data.upsell.title}
          description={data.upsell.body}
          feature="weekly_roundup"
          leagueName={leagueName}
        />
      ) : null}

      <AppText style={styles.method}>{data.method}</AppText>
    </View>
  );
}

function Stat({
  label,
  value,
  color,
  styles,
}: {
  label: string;
  value: string;
  color?: string;
  styles: ReturnType<typeof createStyles>;
}) {
  return (
    <View style={styles.stat}>
      <AppText style={[styles.statValue, color ? { color } : null]}>{value}</AppText>
      <AppText style={styles.statLabel}>{label.toUpperCase()}</AppText>
    </View>
  );
}

function SwapCard({ swap }: { swap: RoundupSwap }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const accent = accentTokenColor(colors, predictabilityToken(swap.predictability));
  return (
    <AccentCard accent={accent} compact>
      <View style={styles.swapHeader}>
        <AppText style={[styles.tag, { color: accent }]}>{PREDICTABILITY_LABEL[swap.predictability].toUpperCase()}</AppText>
        <AppText style={styles.gain}>+{formatPoints(swap.gain)} pts</AppText>
      </View>
      <AppText style={styles.swapLine}>{swapLine(swap)}</AppText>
      <View style={styles.reasonRow}>
        <PositionBadge position={swap.slot} />
        <AppText style={[styles.muted, styles.reasonText]}>{swap.reason}</AppText>
      </View>
      {swap.started_projection && swap.benched_projection ? (
        <AppText style={styles.small}>
          Projected before the week: {swap.started.name} {formatPoints(swap.started_projection.points)}, {swap.benched.name}{' '}
          {formatPoints(swap.benched_projection.points)}
        </AppText>
      ) : null}
    </AccentCard>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    content: { padding: spacing.lg, gap: spacing.md },
    stack: { gap: spacing.md },
    kicker: { fontSize: 11.5, fontWeight: '800', letterSpacing: 0.6, color: colors.textTertiary },
    heading: { fontSize: 20, fontWeight: '800', color: colors.textPrimary },
    statRow: { flexDirection: 'row', justifyContent: 'space-between' },
    stat: { flex: 1, alignItems: 'center', gap: 2 },
    statValue: { fontSize: 22, fontWeight: '800', color: colors.textPrimary },
    statLabel: { fontSize: 10.5, fontWeight: '700', letterSpacing: 0.5, color: colors.textTertiary },
    body: { fontSize: 14, lineHeight: 20, color: colors.textPrimary },
    sectionTitle: { fontSize: 15, fontWeight: '800', color: colors.textPrimary },
    muted: { fontSize: 13, color: colors.textSecondary },
    small: { fontSize: 12, color: colors.textTertiary },
    method: { fontSize: 12, lineHeight: 17, color: colors.textTertiary },
    swapHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
    tag: { fontSize: 11.5, fontWeight: '800', letterSpacing: 0.6 },
    gain: { fontSize: 14, fontWeight: '800', color: colors.textPrimary },
    swapLine: { fontSize: 14, fontWeight: '700', color: colors.textPrimary },
    reasonRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
    reasonText: { flex: 1 },
    lineupCard: { borderWidth: 1, borderColor: colors.cardBorder, borderRadius: radii.md, padding: spacing.md, gap: spacing.sm },
    lineupRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
    slotCell: { width: 52 },
    lineupName: { flex: 1, fontSize: 13, color: colors.textPrimary },
    regretRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
    regretWeek: { width: 40, fontSize: 12, color: colors.textTertiary },
    regretTrack: { flex: 1, height: 8, borderRadius: 4, backgroundColor: colors.cardBorder, overflow: 'hidden' },
    regretFill: { height: 8, borderRadius: 4 },
    regretValue: { width: 44, textAlign: 'right', fontSize: 12, fontWeight: '700', color: colors.textPrimary },
  });
}
