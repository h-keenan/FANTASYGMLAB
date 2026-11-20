import React, { useMemo } from 'react';
import { StyleSheet, View } from 'react-native';

import AppText from './AppText';
import CompactModule from './CompactModule';
import CompactPlayerCard from './CompactPlayerCard';
import { useThemeMode } from '../context/ThemeModeContext';
import {
  depthChange,
  depthChartParts,
  depthPlace,
  depthRoleLabel,
  depthRowKind,
  injuryCoverageNote,
  injuryHistoryRows,
  injurySummaryParts,
  type DepthChartData,
  type InjuryRecordData,
} from '../lib/playerDepthInjury';
import { spacing, type ThemeColors } from '../theme';

/**
 * Depth chart section of the Player Quick View (twin of web-next PlayerDepthInjury.tsx): the player's real NFL team
 * at his slot in the team's own order, his row highlighted, who is ahead and behind (each row opens that player's
 * quick view) and any move since the last weekly reading. Data-driven so the Fantasy Sim can pass a simulated chart.
 * `chart === undefined` = loading; null / not on a chart renders nothing. Collapsed by default.
 */
export function DepthChartSection({ chart, idPrefix = 'pqv' }: { chart: DepthChartData | null | undefined; idPrefix?: string }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  if (chart === undefined) return <CompactModule id={`${idPrefix}.depth`} title="Depth chart" parts={[]} loading testID="pqv-depth-loading" />;
  const parts = depthChartParts(chart);
  if (!chart || parts.length === 0) return null;
  return (
    <CompactModule id={`${idPrefix}.depth`} title="Depth chart" label={`Depth chart, ${chart.slot_label ?? chart.slot ?? ''}`} parts={parts} tone="accent" testID="pqv-depth">
      <AppText style={styles.muted}>
        {chart.team} {chart.slot_label ?? chart.slot} · {chart.total} on the chart
      </AppText>
      <View style={styles.list} accessibilityLabel="Depth chart order">
        {chart.entries.map((entry) => {
          const kind = depthRowKind(entry, chart.self_rank ?? chart.self_order);
          const moved = depthChange(entry.change);
          const detail = [depthRoleLabel(chart.slot, depthPlace(entry)), kind === 'ahead' ? 'Ahead' : kind === 'behind' ? 'Behind' : 'This player', entry.injury_status]
            .filter(Boolean)
            .join(' · ');
          return (
            <View key={entry.player_id} style={[styles.row, entry.is_self ? styles.self : null]} testID="pqv-depth-row" accessibilityState={{ selected: entry.is_self }}>
              <CompactPlayerCard
                player={{ id: entry.player_id, name: entry.name, position: entry.position, team: entry.team }}
                detail={detail}
                nonInteractive={entry.is_self ? 'this is the player whose quick view is already open' : undefined}
                trailing={
                  moved ? (
                    <AppText style={{ color: moved.tone === 'success' ? colors.success : colors.danger, fontWeight: '800', fontSize: 13 }} testID="pqv-depth-move">
                      {moved.arrow === 'up' ? '▲' : '▼'} {moved.text}
                    </AppText>
                  ) : null
                }
              />
            </View>
          );
        })}
      </View>
      <AppText style={styles.muted}>Order is the team&apos;s own listing; moves compare with last week.</AppText>
    </CompactModule>
  );
}

/**
 * Injury section (twin of the web one): the current injury line ("Hamstring · Questionable") with practice status
 * in the collapsed summary, and on tap a compact history, one row per stint (season, injury, weeks, games missed)
 * plus the career total. `record === undefined` = loading; null renders nothing.
 */
export function InjuryHistorySection({ record, idPrefix = 'pqv' }: { record: InjuryRecordData | null | undefined; idPrefix?: string }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  if (record === undefined) return <CompactModule id={`${idPrefix}.injury`} title="Injury history" parts={[]} loading testID="pqv-injury-loading" />;
  if (!record || !record.ok) return null;
  const rows = injuryHistoryRows(record);
  const note = injuryCoverageNote(record);
  const practice = record.current?.practice;
  const parts = injurySummaryParts(record);
  return (
    <CompactModule
      id={`${idPrefix}.injury`}
      title="Injury history"
      parts={practice ? [...parts.slice(0, 1), { key: 'practice', text: practice, tone: 'muted' as const }, ...parts.slice(1)] : parts}
      tone={record.current ? (record.current.unavailable ? 'danger' : 'warning') : 'success'}
      testID="pqv-injury"
    >
      {record.current?.report ? <AppText style={styles.body}>{record.current.report}</AppText> : null}
      {rows.length === 0 ? (
        <AppText style={styles.muted}>No missed games on record.</AppText>
      ) : (
        <View style={styles.table} testID="pqv-injury-rows">
          {rows.map((row) => (
            <View key={row.key} style={styles.tr} testID="pqv-injury-row">
              <AppText style={styles.season}>{row.seasonLabel}</AppText>
              <View style={styles.what}>
                <AppText style={styles.body}>
                  {row.injury}
                  {row.weeks ? <AppText style={styles.muted}> · {row.weeks}</AppText> : null}
                </AppText>
              </View>
              <AppText style={styles.games}>{row.games}</AppText>
            </View>
          ))}
          <View style={[styles.tr, styles.total]}>
            <AppText style={styles.career}>Career games missed</AppText>
            <AppText style={styles.games} testID="pqv-injury-career">{record.career_games_missed}</AppText>
          </View>
        </View>
      )}
      {note ? <AppText style={styles.muted}>{note}</AppText> : null}
    </CompactModule>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    muted: { fontSize: 12, color: colors.textTertiary },
    body: { fontSize: 14, color: colors.textPrimary },
    list: { gap: 4 },
    row: { borderRadius: 8, paddingHorizontal: spacing.xs },
    self: { backgroundColor: `${colors.accent}24`, borderLeftWidth: 2, borderLeftColor: colors.accent },
    table: { gap: 2 },
    tr: { flexDirection: 'row', alignItems: 'flex-start', gap: spacing.sm },
    season: { width: 72, fontSize: 14, color: colors.textPrimary, fontVariant: ['tabular-nums'] },
    what: { flex: 1, minWidth: 0 },
    games: { fontSize: 14, color: colors.textPrimary, textAlign: 'right', fontVariant: ['tabular-nums'] },
    total: { marginTop: 2, justifyContent: 'space-between' },
    career: { fontSize: 14, fontWeight: '800', color: colors.textPrimary },
  });
}
