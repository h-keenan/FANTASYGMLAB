import React, { useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { Animated, StyleSheet, TouchableOpacity, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import AppText from './AppText';
import OvrGauge from './OvrGauge';
import PlayerAvatar from './PlayerAvatar';
import PlayerNameText from './PlayerNameText';
import PositionBadge from './PositionBadge';
import TickNumber from './TickNumber';
import ToneBadge from './ToneBadge';
import { useThemeMode } from '../context/ThemeModeContext';
import {
  PLAYER_CARD_AVATAR_SIZE,
  formatCardPoints,
  headlinePoints,
  playerCardAriaLabel,
  playerGameLine,
  playerStatusChips,
  trendVsProjection,
  type ChipTone,
  type PlayerCardModel,
  type PlayerCardVariant,
} from '../lib/playerCard';
import { positionColor, radii, spacing, type ThemeColors } from '../theme';

/**
 * THE player card (docs/player-card.md); twin of web-next's PlayerCardKit.
 * Three variants so a player looks the same everywhere:
 *  - `compact`: list row (photo, name, position/team, status chips, 1-2 stats).
 *  - `matchup`: head-to-head row (live/final points big, projected final with a
 *    green/red trend, game line, game-progress bar, expandable detail).
 *  - `card`: larger tile with the value (OVR) ring.
 * Tapping opens the shared Player Quick View through `onPress`. What it says
 * comes from lib/playerCard.ts (shared with web).
 */

export interface PlayerCardStat {
  label: string;
  value: string;
}

function chipColor(colors: ThemeColors, tone: ChipTone): string {
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

export function PlayerStatusChips({ model }: { model: PlayerCardModel }) {
  const { colors } = useThemeMode();
  return (
    <>
      {playerStatusChips(model).map((chip) => (
        <ToneBadge
          key={chip.kind}
          size="xs"
          label={chip.kind === 'live' ? '● LIVE' : chip.label}
          color={chipColor(colors, chip.tone)}
        />
      ))}
    </>
  );
}

export interface PlayerCardProps {
  variant: PlayerCardVariant;
  model: PlayerCardModel;
  /** Opens Player Quick View (or the planner swap sheet when `editing`). */
  onPress?: () => void;
  /** Planner mode: the tap swaps instead of opening Quick View. */
  editing?: boolean;
  /** Matchup: mirror the layout so numbers face the center (side-by-side layouts only). */
  mirror?: boolean;
  emphasis?: 'win' | 'lose' | 'even';
  stats?: PlayerCardStat[];
  /** Matchup: bump to re-run the "points just changed" pulse. */
  pulseKey?: number;
  detail?: ReactNode;
  /** Matchup: "YOU" / "OPP" tag, since the two cards are stacked on phones. */
  sideTag?: 'you' | 'opp';
  trailing?: ReactNode;
}

export function PlayerCard(props: PlayerCardProps) {
  if (props.variant === 'matchup') return <MatchupCard {...props} />;
  if (props.variant === 'card') return <TileCard {...props} />;
  return <CompactCard {...props} />;
}

function useCardStyles() {
  const { colors, isDark } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return { colors, isDark, styles };
}

function Tappable({
  onPress,
  label,
  style,
  children,
}: {
  onPress?: () => void;
  label: string;
  style?: object;
  children: ReactNode;
}) {
  if (!onPress) return <View style={style}>{children}</View>;
  return (
    <TouchableOpacity style={style} onPress={onPress} accessibilityRole="button" accessibilityLabel={label}>
      {children}
    </TouchableOpacity>
  );
}

function CompactCard({ model, onPress, stats = [], trailing }: PlayerCardProps) {
  const { colors, isDark, styles } = useCardStyles();
  const accent = positionColor(model.position, isDark, colors.borderStrong);
  return (
    <View style={styles.card} testID="player-card-compact">
      <View style={[styles.accent, { backgroundColor: accent }]} />
      <View style={styles.row}>
        <Tappable onPress={onPress} label={playerCardAriaLabel(model)} style={[styles.row, styles.flex]}>
          <PlayerAvatar
            playerId={model.playerId}
            tier={model.tier}
            size={PLAYER_CARD_AVATAR_SIZE.compact}
            fallbackLabel={model.team}
          />
          <View style={styles.flex}>
            <PlayerNameText name={model.name} threshold={Infinity} style={styles.name} />
            <View style={styles.chipRow}>
              <PositionBadge position={model.position} />
              {model.team ? <AppText style={styles.muted}>{model.team}</AppText> : null}
              <PlayerStatusChips model={model} />
            </View>
          </View>
        </Tappable>
        {stats.slice(0, 2).map((stat) => (
          <View key={stat.label} style={styles.stat}>
            <AppText style={styles.statValue}>{stat.value}</AppText>
            <AppText style={styles.statLabel}>{stat.label}</AppText>
          </View>
        ))}
        {trailing}
      </View>
    </View>
  );
}

function TileCard({ model, onPress, stats = [], trailing }: PlayerCardProps) {
  const { colors, isDark, styles } = useCardStyles();
  const accent = positionColor(model.position, isDark, colors.borderStrong);
  return (
    <View style={[styles.card, { gap: spacing.sm }]} testID="player-card-tile">
      <View style={[styles.accent, { backgroundColor: accent }]} />
      <Tappable onPress={onPress} label={playerCardAriaLabel(model)} style={{ gap: spacing.sm }}>
        <View style={styles.tileTop}>
          <PlayerAvatar
            playerId={model.playerId}
            tier={model.tier}
            size={PLAYER_CARD_AVATAR_SIZE.card}
            fallbackLabel={model.team}
          />
          <OvrGauge rating={model.overallRating} size="md" reserveSpace />
        </View>
        <PlayerNameText name={model.name} threshold={Infinity} style={styles.name} />
        <View style={styles.chipRow}>
          <PositionBadge position={model.position} />
          <PlayerStatusChips model={model} />
        </View>
        <AppText style={styles.muted}>{playerGameLine(model) || model.team || ''}</AppText>
      </Tappable>
      {stats.length > 0 ? (
        <View style={styles.row}>
          {stats.slice(0, 3).map((stat) => (
            <View key={stat.label} style={styles.flex}>
              <AppText style={styles.statValue}>{stat.value}</AppText>
              <AppText style={styles.statLabel}>{stat.label}</AppText>
            </View>
          ))}
        </View>
      ) : null}
      {trailing}
    </View>
  );
}

function trendColor(colors: ThemeColors, dir: 'up' | 'down' | 'flat'): string {
  return dir === 'up' ? colors.successBright : dir === 'down' ? colors.danger : colors.textTertiary;
}

export function PlayerCardDetail({ model }: { model: PlayerCardModel }) {
  const { styles } = useCardStyles();
  const rows: [string, string][] = [];
  if (model.projection != null) rows.push(['Pre-game projection', formatCardPoints(model.projection)]);
  if (model.points != null) rows.push(['Points so far', formatCardPoints(model.points)]);
  if (model.projectedFinal != null) rows.push(['Projected final', formatCardPoints(model.projectedFinal)]);
  if (model.overallRating != null) rows.push(['Overall rating', String(Math.round(model.overallRating))]);
  if (model.slot) rows.push(['Lineup slot', model.slot]);
  if (model.injuryLabel) rows.push(['Injury status', model.injuryLabel]);
  if (rows.length === 0) return <AppText style={styles.muted}>No more detail yet.</AppText>;
  return (
    <View style={{ gap: 2 }}>
      {rows.map(([term, value]) => (
        <View key={term} style={styles.detailRow}>
          <AppText style={styles.muted}>{term}</AppText>
          <AppText style={styles.detailValue}>{value}</AppText>
        </View>
      ))}
    </View>
  );
}

function PulseOverlay({ pulseKey }: { pulseKey: number }) {
  const { colors, styles } = useCardStyles();
  const opacity = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    if (pulseKey <= 0) return;
    opacity.setValue(0.85);
    Animated.timing(opacity, { toValue: 0, duration: 1400, useNativeDriver: true }).start();
  }, [pulseKey, opacity]);
  return <Animated.View pointerEvents="none" style={[styles.pulse, { borderColor: colors.successBright, opacity }]} />;
}

function MatchupCard({ model, onPress, editing, mirror = false, emphasis = 'even', pulseKey = 0, detail, sideTag }: PlayerCardProps) {
  const { colors, isDark, styles } = useCardStyles();
  const [open, setOpen] = useState(false);
  const head = headlinePoints(model);
  const trend = trendVsProjection(model);
  const accent = positionColor(model.position, isDark, colors.borderStrong);
  const unavailable = model.bye || model.out;
  const align = mirror ? 'flex-end' : 'flex-start';
  const pointsLabel =
    head.kind === 'pts' ? (model.gameStatus === 'final' ? 'FINAL PTS' : 'PTS') : head.kind === 'proj' ? 'PROJ' : model.bye ? 'BYE' : '';
  return (
    <View
      style={[
        styles.card,
        emphasis === 'win' && { backgroundColor: colors.accentMuted, borderColor: colors.accent },
        unavailable && { borderStyle: 'dashed' },
      ]}
      testID="player-card-matchup"
    >
      <View style={[styles.accent, { backgroundColor: accent }]} />
      {pulseKey > 0 ? <PulseOverlay pulseKey={pulseKey} /> : null}
      <View style={[styles.row, mirror && styles.rowReverse]}>
        <Tappable
          onPress={onPress}
          label={editing ? `Swap ${model.name}` : playerCardAriaLabel(model)}
          style={[styles.row, styles.flex, mirror && styles.rowReverse]}
        >
          <PlayerAvatar
            playerId={model.playerId}
            tier={model.tier}
            size={PLAYER_CARD_AVATAR_SIZE.matchup}
            fallbackLabel={model.team}
          />
          <View style={[styles.flex, { alignItems: align, gap: 3 }]}>
            <PlayerNameText name={model.name} threshold={Infinity} style={[styles.name, mirror && styles.textRight]} />
            <View style={[styles.chipRow, mirror && { justifyContent: 'flex-end' }]}>
              {sideTag ? (
                <ToneBadge size="xs" label={sideTag === 'you' ? 'YOU' : 'OPP'} color={sideTag === 'you' ? colors.accent : colors.textTertiary} />
              ) : null}
              <PositionBadge position={model.position} />
              <PlayerStatusChips model={model} />
            </View>
            <AppText style={[styles.muted, mirror && styles.textRight]} numberOfLines={1}>
              {[model.team, playerGameLine(model)].filter(Boolean).join(' · ')}
            </AppText>
          </View>
        </Tappable>
        <View style={{ alignItems: mirror ? 'flex-start' : 'flex-end', gap: 2 }}>
          {head.value != null ? (
            <TickNumber
              value={head.value}
              testID="player-card-points"
              style={[
                styles.points,
                { color: head.kind === 'pts' ? colors.textPrimary : colors.textSecondary },
                emphasis === 'lose' && { color: colors.textTertiary },
              ]}
            />
          ) : (
            <AppText style={[styles.points, { color: colors.textTertiary }]}>{unavailable ? '0.0' : '—'}</AppText>
          )}
          {pointsLabel ? <AppText style={styles.statLabel}>{pointsLabel}</AppText> : null}
          {model.projectedFinal != null ? (
            <View style={styles.trendRow} testID="proj-final">
              {trend ? (
                <Ionicons
                  name={trend.dir === 'up' ? 'arrow-up' : trend.dir === 'down' ? 'arrow-down' : 'remove'}
                  size={11}
                  color={trendColor(colors, trend.dir)}
                />
              ) : null}
              <AppText style={[styles.trendText, { color: trend ? trendColor(colors, trend.dir) : colors.textSecondary }]}>
                Proj final {model.projectedFinal.toFixed(1)}
              </AppText>
            </View>
          ) : model.gameStatus === 'final' && trend ? (
            <View style={styles.trendRow}>
              <Ionicons
                name={trend.dir === 'up' ? 'arrow-up' : trend.dir === 'down' ? 'arrow-down' : 'remove'}
                size={11}
                color={trendColor(colors, trend.dir)}
              />
              <AppText style={[styles.trendText, { color: trendColor(colors, trend.dir) }]}>
                {trend.delta > 0 ? '+' : ''}
                {trend.delta.toFixed(1)} vs proj
              </AppText>
            </View>
          ) : null}
        </View>
      </View>
      {model.gameStatus ? (
        <View
          style={styles.progressTrack}
          accessibilityRole="progressbar"
          accessibilityLabel="Game progress"
          accessibilityValue={{ min: 0, max: 100, now: Math.round(model.progress * 100) }}
        >
          <View
            style={[
              styles.progressFill,
              {
                width: `${Math.round(model.progress * 100)}%`,
                backgroundColor: model.gameStatus === 'final' ? colors.textTertiary : colors.successBright,
              },
            ]}
          />
        </View>
      ) : null}
      <TouchableOpacity
        onPress={() => setOpen((value) => !value)}
        accessibilityRole="button"
        accessibilityState={{ expanded: open }}
        accessibilityLabel={open ? `Hide ${model.name} details` : `Show ${model.name} details`}
        style={styles.expandRow}
      >
        <Ionicons name={open ? 'chevron-up' : 'chevron-down'} size={12} color={colors.textTertiary} />
        <AppText style={styles.expandText}>{open ? 'Less' : 'Details'}</AppText>
      </TouchableOpacity>
      {open ? <View>{detail ?? <PlayerCardDetail model={model} />}</View> : null}
    </View>
  );
}

/** Placeholder card for an open lineup slot. */
export function EmptySlotCard({ onPress }: { onPress?: () => void }) {
  const { colors, styles } = useCardStyles();
  return (
    <View style={[styles.card, { minHeight: 64, justifyContent: 'center', borderStyle: 'dashed' }]} testID="player-card-empty">
      {onPress ? (
        <TouchableOpacity onPress={onPress} accessibilityRole="button">
          <AppText style={[styles.empty, { color: colors.accent }]}>Empty, tap to fill</AppText>
        </TouchableOpacity>
      ) : (
        <AppText style={styles.empty}>Empty slot</AppText>
      )}
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    card: {
      position: 'relative',
      overflow: 'hidden',
      gap: 6,
      paddingVertical: 10,
      paddingLeft: 15,
      paddingRight: 12,
      borderRadius: radii.md,
      borderWidth: 1,
      borderColor: colors.glassInputBorder,
      backgroundColor: colors.glassInput,
    },
    accent: { position: 'absolute', left: 0, top: 9, bottom: 9, width: 3, borderRadius: 3 },
    row: { flexDirection: 'row', alignItems: 'center', gap: 10, minWidth: 0 },
    rowReverse: { flexDirection: 'row-reverse' },
    flex: { flex: 1, minWidth: 0 },
    chipRow: { flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', gap: 4, minWidth: 0 },
    name: { fontSize: 15, fontWeight: '700', color: colors.textPrimary, alignSelf: 'stretch' },
    textRight: { textAlign: 'right' },
    muted: { fontSize: 12.5, color: colors.textTertiary },
    stat: { alignItems: 'flex-end' },
    statValue: { fontSize: 15, fontWeight: '800', color: colors.textPrimary, fontVariant: ['tabular-nums'] },
    statLabel: { fontSize: 11, fontWeight: '700', letterSpacing: 0.6, color: colors.textTertiary, textTransform: 'uppercase' },
    tileTop: { flexDirection: 'row', alignItems: 'flex-start', justifyContent: 'space-between' },
    points: { fontSize: 22, fontWeight: '800', lineHeight: 24 },
    trendRow: { flexDirection: 'row', alignItems: 'center', gap: 2 },
    trendText: { fontSize: 12, fontWeight: '700', fontVariant: ['tabular-nums'] },
    progressTrack: { height: 3, borderRadius: 2, backgroundColor: colors.border, overflow: 'hidden' },
    progressFill: { height: '100%', borderRadius: 2 },
    expandRow: { flexDirection: 'row', alignItems: 'center', gap: 4, alignSelf: 'flex-start', paddingVertical: 2 },
    expandText: { fontSize: 12, fontWeight: '700', color: colors.textTertiary },
    detailRow: { flexDirection: 'row', justifyContent: 'space-between' },
    detailValue: { fontSize: 13, fontWeight: '700', color: colors.textPrimary, fontVariant: ['tabular-nums'] },
    pulse: { ...StyleSheet.absoluteFillObject, borderRadius: radii.md, borderWidth: 2 },
    empty: { fontSize: 13.5, fontStyle: 'italic', color: colors.textTertiary },
  });
}
