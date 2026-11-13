import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Animated, StyleSheet, TouchableOpacity, View } from 'react-native';

import AppText from './AppText';
import PlayerName from './PlayerName';
import { PlayerCard } from './PlayerCardKit';
import PlayerAvatar from './PlayerAvatar';
import PositionBadge from './PositionBadge';
import SegmentedTabBar from './SegmentedTabBar';
import TickNumber from './TickNumber';
import ToneBadge from './ToneBadge';
import { useThemeMode } from '../context/ThemeModeContext';
import type { MatchupSide, MatchupWinProbability } from '../lib/api';
import { changedPlayerIds, slotTotals, sortSlots, type SlotComparison, type SlotSortMode } from '../lib/lineupSlots';
import { freshnessLabel } from '../lib/liveScores';
import { formatSigned, type LineupPlayer } from '../lib/matchupPresentation';
import { headlinePoints, playerCardAriaLabel, playerStatusChips, trendVsProjection, type ChipTone } from '../lib/playerCard';
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

/** Status as color AND shape: live = filled dot, upcoming = hollow ring, final = check, bye = dash, out = x. */
const STATUS_GLYPH: Record<string, string> = { live: '●', upcoming: '○', final: '✓', bye: '–', out: '✕' };

function dotColor(colors: ThemeColors, tone: ChipTone): string {
  switch (tone) {
    case 'success':
      return colors.successBright;
    case 'danger':
      return colors.danger;
    case 'warning':
      return colors.warning;
    case 'accent':
      return colors.accent;
    default:
      return colors.textTertiary;
  }
}

function CompactSide({
  cell,
  mirror,
  emphasis,
  pulseKey,
  onPress,
}: {
  cell: SlotComparison['mine'];
  mirror: boolean;
  emphasis: 'win' | 'lose' | 'even';
  pulseKey: number;
  onPress?: () => void;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  if (cell.kind === 'none') return <View style={styles.flex} />;
  if (cell.kind === 'empty') {
    return (
      <View style={styles.flex}>
        <AppText style={styles.empty}>{onPress ? 'Empty, tap to fill' : 'Empty slot'}</AppText>
      </View>
    );
  }
  const card = cell.card;
  const head = headlinePoints(card);
  const trend = trendVsProjection(card);
  const chips = playerStatusChips(card);
  const primary = chips[0];
  const flag = chips.find((chip) => chip.kind === 'questionable' || chip.kind === 'doubtful');
  const align = mirror ? 'flex-end' : 'flex-start';
  const trendColor = trend ? (trend.dir === 'up' ? colors.successBright : trend.dir === 'down' ? colors.danger : colors.textTertiary) : colors.textSecondary;
  return (
    <TouchableOpacity
      style={[
        styles.flex,
        styles.side,
        mirror && { flexDirection: 'row-reverse' },
        emphasis === 'win' && { backgroundColor: colors.accentMuted },
      ]}
      onPress={onPress}
      disabled={!onPress}
      accessibilityRole="button"
      accessibilityLabel={playerCardAriaLabel(card)}
    >
      {pulseKey > 0 ? <PulseRing pulseKey={pulseKey} /> : null}
      <PlayerAvatar playerId={card.playerId} tier={card.tier} size={36} fallbackLabel={card.team} />
      <View style={[styles.flex, { alignItems: align, gap: 1 }]}>
        <PlayerName name={card.name} style={[styles.sideName, mirror && { textAlign: 'right' }]} />
        <View style={[styles.statusRow, mirror && { flexDirection: 'row-reverse' }]}>
          {primary ? (
            <AppText
              style={[styles.statusText, { color: dotColor(colors, primary.tone) }]}
              accessibilityLabel={primary.label}
            >
              {STATUS_GLYPH[primary.kind] ?? '●'}
            </AppText>
          ) : null}
          {flag ? <AppText style={[styles.statusText, { color: dotColor(colors, flag.tone) }]}>{flag.kind === 'doubtful' ? 'D' : 'Q'}</AppText> : null}
        </View>
        <View style={[styles.statusRow, mirror && { flexDirection: 'row-reverse' }, { gap: 6 }]}>
          {head.value != null ? (
            <TickNumber
              value={head.value}
              style={[styles.sidePoints, { color: emphasis === 'lose' ? colors.textTertiary : colors.textPrimary }]}
            />
          ) : (
            <AppText style={[styles.sidePoints, { color: colors.textTertiary }]}>{card.bye || card.out ? '0.0' : '—'}</AppText>
          )}
          {card.projectedFinal != null ? (
            <AppText style={[styles.statusText, { color: trendColor }]}>
              {trend ? (trend.dir === 'up' ? '▲' : trend.dir === 'down' ? '▼' : '–') : ''}
              {card.projectedFinal.toFixed(1)}
            </AppText>
          ) : head.kind === 'proj' ? (
            <AppText style={[styles.statusText, { color: colors.textTertiary }]}>PROJ</AppText>
          ) : null}
        </View>
      </View>
    </TouchableOpacity>
  );
}

function PulseRing({ pulseKey }: { pulseKey: number }) {
  const { colors } = useThemeMode();
  const opacity = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    opacity.setValue(0.85);
    Animated.timing(opacity, { toValue: 0, duration: 1400, useNativeDriver: true }).start();
  }, [pulseKey, opacity]);
  return (
    <Animated.View
      pointerEvents="none"
      style={[StyleSheet.absoluteFillObject, { borderRadius: radii.md, borderWidth: 2, borderColor: colors.successBright, opacity }]}
    />
  );
}

/** Phone row: [my player] [slot label + lead bar + margin, tap to expand] [opponent mirrored]. */
export function SlotRow({
  slot,
  pulses,
  onPressPlayer,
  onEditMine,
  open,
  onToggle,
}: {
  slot: SlotComparison;
  pulses: Map<string, number>;
  onPressPlayer: (player: LineupPlayer) => void;
  onEditMine?: () => void;
  open: boolean;
  onToggle: () => void;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const emphasis = (side: 'mine' | 'opponent') =>
    slot.leader == null || slot.leader === 'tie' ? 'even' : slot.leader === side ? 'win' : 'lose';
  const pulse = (cell: SlotComparison['mine']) => (cell.kind === 'player' && cell.card.playerId ? (pulses.get(cell.card.playerId) ?? 0) : 0);
  const lead = slot.leader === 'mine' ? slot.margin : slot.leader === 'opponent' ? -slot.margin : 0;
  const share = slot.barShare;
  return (
    <View
      style={[styles.slotRow, slot.decides && { borderColor: colors.warning, backgroundColor: colors.warningMuted }]}
      testID="slot-row"
    >
      <View style={styles.compactGrid}>
        <CompactSide
          cell={slot.mine}
          mirror={false}
          emphasis={emphasis('mine')}
          pulseKey={pulse(slot.mine)}
          onPress={onEditMine ?? (slot.mine.kind === 'player' ? () => onPressPlayer((slot.mine as { source: LineupPlayer }).source) : undefined)}
        />
        <TouchableOpacity
          style={styles.compactCenter}
          onPress={onToggle}
          accessibilityRole="button"
          accessibilityState={{ expanded: open }}
          accessibilityLabel={`${slot.label} details`}
        >
          <PositionBadge position={slot.slot} label={slot.label} />
          <View style={styles.barTrack}>
            <View style={[styles.barFill, { width: `${share ?? 50}%`, opacity: share == null ? 0.25 : 1 }]} />
          </View>
          <AppText style={[styles.leadSmall, { color: leadColor(colors, lead) }]}>
            {slot.leader == null ? '—' : slot.leader === 'tie' ? 'Even' : formatSigned(lead)}
            {open ? ' ▴' : ' ▾'}
          </AppText>
        </TouchableOpacity>
        <CompactSide
          cell={slot.opponent}
          mirror
          emphasis={emphasis('opponent')}
          pulseKey={pulse(slot.opponent)}
          onPress={slot.opponent.kind === 'player' ? () => onPressPlayer((slot.opponent as { source: LineupPlayer }).source) : undefined}
        />
      </View>
      {open ? (
        <View style={{ gap: 6, paddingTop: 6 }} testID="slot-expanded">
          {([['mine', slot.mine], ['opponent', slot.opponent]] as const).map(([side, cell]) =>
            cell.kind === 'player' ? (
              <PlayerCard
                key={side}
                variant="matchup"
                model={cell.card}
                emphasis={emphasis(side)}
                sideTag={side === 'mine' ? 'you' : 'opp'}
                onPress={() => onPressPlayer(cell.source)}
              />
            ) : null,
          )}
        </View>
      ) : null}
    </View>
  );
}

function Legend() {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const items: [string, string, string][] = [
    ['live', 'LIVE', colors.successBright],
    ['upcoming', 'UPCOMING', colors.accent],
    ['final', 'FINAL', colors.textTertiary],
    ['bye', 'BYE', colors.warning],
    ['out', 'OUT', colors.danger],
  ];
  return (
    <View style={styles.legend}>
      {items.map(([kind, label, color]) => (
        <View key={label} style={styles.statusRow}>
          <AppText style={[styles.statusText, { color }]}>{STATUS_GLYPH[kind]}</AppText>
          <AppText style={styles.statusText}>{label}</AppText>
        </View>
      ))}
      <AppText style={styles.statusText}>DECIDES = amber ring · tap middle to expand</AppText>
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
  const [openKey, setOpenKey] = useState<string | null>(null);
  return (
    <View style={{ gap: spacing.xs }}>
      <Legend />
      {ordered.map((slot) => (
        <SlotRow
          key={slot.key}
          slot={slot}
          pulses={pulses}
          onPressPlayer={onPressPlayer}
          onEditMine={planEditIndex?.(slot)}
          open={openKey === slot.key}
          onToggle={() => setOpenKey((current) => (current === slot.key ? null : slot.key))}
        />
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
    compactGrid: { flexDirection: 'row', alignItems: 'center', gap: 2 },
    compactCenter: { width: 52, alignItems: 'center', gap: 4 },
    side: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingVertical: 4, paddingHorizontal: 3, borderRadius: radii.md },
    sideName: { fontSize: 13, fontWeight: '700', color: colors.textPrimary, alignSelf: 'stretch' },
    sidePoints: { fontSize: 17, fontWeight: '800', fontVariant: ['tabular-nums'] },
    statusRow: { flexDirection: 'row', alignItems: 'center', gap: 3 },
    statusText: { fontSize: 12, fontWeight: '800', letterSpacing: 0.3, color: colors.textTertiary, fontVariant: ['tabular-nums'] },
    dot: { width: 6, height: 6, borderRadius: 3 },
    empty: { fontSize: 12.5, fontStyle: 'italic', color: colors.textTertiary },
    leadSmall: { fontSize: 12, fontWeight: '800', fontVariant: ['tabular-nums'] },
    legend: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm, alignItems: 'center' },
    center: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, paddingHorizontal: 4 },
    barTrack: { flex: 1, height: 4, borderRadius: 2, backgroundColor: colors.border, overflow: 'hidden' },
    barFill: { height: '100%', backgroundColor: colors.successBright },
    lead: { fontSize: 12.5, fontWeight: '800', minWidth: 44, textAlign: 'right', fontVariant: ['tabular-nums'] },
  });
}
