import React, { useEffect, useMemo, useRef, useState } from 'react';
import { StyleSheet, View } from 'react-native';

import AppText from './AppText';
import { EmptySlotCard, PlayerCard } from './PlayerCardKit';
import PositionBadge from './PositionBadge';
import SegmentedTabBar from './SegmentedTabBar';
import TickNumber from './TickNumber';
import ToneBadge from './ToneBadge';
import { useThemeMode } from '../context/ThemeModeContext';
import type { MatchupSide, MatchupWinProbability } from '../lib/api';
import { changedPlayerIds, slotTotals, sortSlots, type SlotComparison, type SlotSortMode } from '../lib/lineupSlots';
import { freshnessLabel } from '../lib/liveScores';
import { formatSigned, type LineupPlayer } from '../lib/matchupPresentation';
import { radii, spacing, type ThemeColors } from '../theme';

/**
 * Two-sided, slot-by-slot lineup comparison for phones: my player card, a
 * center slot strip (label + mini win bar + lead), then the opponent's card,
 * per slot. Slot logic: lib/lineupSlots.ts (shared with web). Twin of
 * web-next's MatchupLineup.tsx.
 */

export function usePointPulses(slots: SlotComparison[]): Map<string, number> {
  const previous = useRef<SlotComparison[] | null>(null);
  const [pulses, setPulses] = useState<Map<string, number>>(() => new Map());
  useEffect(() => {
    const changed = changedPlayerIds(previous.current, slots);
    previous.current = slots;
    if (changed.size === 0) return;
    setPulses((current) => {
      const next = new Map(current);
      for (const id of changed) next.set(id, (next.get(id) ?? 0) + 1);
      return next;
    });
  }, [slots]);
  return pulses;
}

function leadColor(colors: ThemeColors, value: number): string {
  if (Math.abs(value) < 0.05) return colors.textTertiary;
  return value > 0 ? colors.successBright : colors.danger;
}

export function ComparisonHeader({
  mine,
  opponent,
  slots,
  odds,
  ageSeconds,
  live,
  sort,
  onSort,
}: {
  mine: MatchupSide;
  opponent: MatchupSide;
  slots: SlotComparison[];
  odds: MatchupWinProbability | null | undefined;
  ageSeconds?: number | null;
  live: boolean;
  sort: SlotSortMode;
  onSort: (mode: SlotSortMode) => void;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const totals = slotTotals(slots);
  const showFinal = slots.some((slot) => slot.remaining >= 1);
  const pct = odds?.available === true && odds.probability != null ? Math.round(odds.probability * 100) : null;
  const leads = slots.filter((slot) => slot.leader === 'mine').length;
  const trails = slots.filter((slot) => slot.leader === 'opponent').length;
  const hasDeciding = slots.some((slot) => slot.decides);
  return (
    <View style={{ gap: spacing.sm }} testID="comparison-header">
      <View style={styles.headerRow}>
        <View style={styles.flex}>
          <AppText style={[styles.teamName, { color: colors.accent }]} numberOfLines={1}>
            {mine.team_name || 'You'}
          </AppText>
          <TickNumber value={totals.mineNow} style={styles.total} />
          {showFinal ? <AppText style={styles.sub}>{`Proj final ${totals.mineFinal.toFixed(1)}`}</AppText> : null}
        </View>
        <View style={{ alignItems: 'center', gap: 4 }}>
          {pct != null ? (
            <AppText style={[styles.winPct, { color: pct >= 50 ? colors.successBright : colors.danger }]}>{`${pct}% win`}</AppText>
          ) : null}
          <ToneBadge
            label={Math.abs(totals.marginNow) < 0.05 ? 'Even' : formatSigned(totals.marginNow)}
            color={leadColor(colors, totals.marginNow)}
          />
        </View>
        <View style={[styles.flex, { alignItems: 'flex-end' }]}>
          <AppText style={[styles.teamName, { color: colors.textPrimary }]} numberOfLines={1}>
            {opponent.team_name || 'Opponent'}
          </AppText>
          <TickNumber value={totals.opponentNow} style={styles.total} />
          {showFinal ? <AppText style={styles.sub}>{`Proj final ${totals.opponentFinal.toFixed(1)}`}</AppText> : null}
        </View>
      </View>
      <AppText style={styles.sub} accessibilityLiveRegion="polite">
        {`You lead ${leads} slot${leads === 1 ? '' : 's'}, trail ${trails}`}
        {ageSeconds != null ? ` · ${freshnessLabel(ageSeconds)}` : live ? ' · Live' : ''}
      </AppText>
      {hasDeciding ? (
        <SegmentedTabBar
          options={[
            { key: 'lineup' as const, label: 'Lineup order' },
            { key: 'decisive' as const, label: 'Deciding first' },
          ]}
          active={sort}
          onChange={onSort}
        />
      ) : null}
    </View>
  );
}

function SlotCenter({ slot }: { slot: SlotComparison }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const share = slot.barShare;
  const lead = slot.leader === 'mine' ? slot.margin : slot.leader === 'opponent' ? -slot.margin : 0;
  return (
    <View style={styles.center} testID="slot-center">
      <PositionBadge position={slot.slot} label={slot.label} size="md" />
      <View
        style={styles.barTrack}
        accessible
        accessibilityLabel={
          share == null
            ? `${slot.label}: no comparison yet`
            : `${slot.label}: you ${Math.round(share)}% of this slot, opponent ${100 - Math.round(share)}%`
        }
      >
        <View style={[styles.barFill, { width: `${share ?? 50}%`, opacity: share == null ? 0.25 : 1 }]} />
      </View>
      <AppText style={[styles.lead, { color: leadColor(colors, lead) }]}>
        {slot.leader == null ? '—' : slot.leader === 'tie' ? 'Even' : formatSigned(lead)}
      </AppText>
      {slot.decides ? <ToneBadge size="xs" label="Decides" color={colors.warning} /> : null}
    </View>
  );
}

export function SlotRow({
  slot,
  pulses,
  onPressPlayer,
  onEditMine,
}: {
  slot: SlotComparison;
  pulses: Map<string, number>;
  onPressPlayer: (player: LineupPlayer) => void;
  onEditMine?: () => void;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const emphasis = (side: 'mine' | 'opponent') =>
    slot.leader == null || slot.leader === 'tie' ? 'even' : slot.leader === side ? 'win' : 'lose';
  const cell = (side: 'mine' | 'opponent') => {
    const value = side === 'mine' ? slot.mine : slot.opponent;
    if (value.kind === 'none') return null;
    if (value.kind === 'empty') return <EmptySlotCard onPress={side === 'mine' ? onEditMine : undefined} />;
    const editing = side === 'mine' && onEditMine != null;
    return (
      <PlayerCard
        variant="matchup"
        model={value.card}
        emphasis={emphasis(side)}
        sideTag={side === 'mine' ? 'you' : 'opp'}
        editing={editing}
        pulseKey={value.card.playerId ? (pulses.get(value.card.playerId) ?? 0) : 0}
        onPress={editing ? onEditMine : () => onPressPlayer(value.source)}
      />
    );
  };
  return (
    <View style={[styles.slotRow, slot.decides && { borderColor: colors.warning, backgroundColor: colors.warningMuted }]} testID="slot-row">
      {cell('mine')}
      <SlotCenter slot={slot} />
      {cell('opponent')}
    </View>
  );
}

export function SlotList({
  slots,
  sort,
  onPressPlayer,
  planEditIndex,
}: {
  slots: SlotComparison[];
  sort: SlotSortMode;
  onPressPlayer: (player: LineupPlayer) => void;
  planEditIndex?: (slot: SlotComparison) => (() => void) | undefined;
}) {
  const pulses = usePointPulses(slots);
  const ordered = useMemo(() => sortSlots(slots, sort), [slots, sort]);
  return (
    <View style={{ gap: spacing.md }}>
      {ordered.map((slot) => (
        <SlotRow key={slot.key} slot={slot} pulses={pulses} onPressPlayer={onPressPlayer} onEditMine={planEditIndex?.(slot)} />
      ))}
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    flex: { flex: 1, minWidth: 0 },
    headerRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
    teamName: { fontSize: 12.5, fontWeight: '700' },
    total: { fontSize: 28, fontWeight: '800', lineHeight: 32, color: colors.textPrimary },
    sub: { fontSize: 12.5, color: colors.textTertiary },
    winPct: { fontSize: 13.5, fontWeight: '800' },
    slotRow: {
      gap: 6,
      padding: 2,
      borderRadius: radii.md,
      borderWidth: 1,
      borderColor: 'transparent',
    },
    center: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, paddingHorizontal: 4 },
    barTrack: { flex: 1, height: 4, borderRadius: 2, backgroundColor: colors.border, overflow: 'hidden' },
    barFill: { height: '100%', backgroundColor: colors.successBright },
    lead: { fontSize: 12.5, fontWeight: '800', minWidth: 44, textAlign: 'right', fontVariant: ['tabular-nums'] },
  });
}
