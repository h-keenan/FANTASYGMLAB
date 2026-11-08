import React, { useMemo, useState } from 'react';
import { StyleSheet, TouchableOpacity, View } from 'react-native';

import { Ionicons } from '@expo/vector-icons';

import AppText from './AppText';
import PlayerAvatar from './PlayerAvatar';
import PositionBadge from './PositionBadge';
import ToneBadge from './ToneBadge';
import ScreenInfoNote from './ScreenInfoNote';
import { useThemeMode } from '../context/ThemeModeContext';
import type { DropPlayer, DropSuggestion, DroppablePlayers, NeedsModel, RosterOverflow } from '../lib/api';
import {
  dropActionLabel,
  overflowHeadline,
  lineupEffectText,
  needTierLabel,
  upgradeText,
  valueEffectText,
  weakestSlotText,
} from '../lib/dropsPresentation';
import { radii, spacing, type ThemeColors } from '../theme';

/**
 * Suggested drops (modules/drop_candidates.py). Mirrors web-next's
 * components/SuggestedDrop.tsx: every value shown is server-computed (the drop,
 * why, the net effect on lineup points and value, alternatives); nothing is
 * ranked or filtered here.
 */

function DropPlayerLine({
  player,
  lead,
  maxReasons = 3,
  swap = false,
  skipReasons,
}: {
  player: DropPlayer;
  lead?: string;
  maxReasons?: number;
  /** The effect is for the whole swap (add minus drop), so say so. */
  swap?: boolean;
  /** Reasons already shown on the main pick, so alternatives don't repeat them. */
  skipReasons?: string[];
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const effectText = [lineupEffectText(player.effect), valueEffectText(player.effect)].filter(Boolean).join(' · ');
  const effect = swap && effectText ? `Whole swap: ${effectText}` : effectText;
  const reasons = player.reasons.filter((reason) => !skipReasons?.includes(reason));
  const pills = effectPills(player.effect, colors);
  const meta = [player.team, player.age ? String(Math.round(player.age)) : ''].filter(Boolean).join(' · ');
  return (
    <View style={styles.playerLine}>
      <View style={styles.nameRow}>
        <PlayerAvatar playerId={player.player_id} size={32} />
        <AppText style={[styles.playerName, { flexShrink: 1 }]}>
          {lead ? `${lead} ` : ''}
          {player.name}
        </AppText>
        <PositionBadge position={player.position} />
        {meta ? <AppText style={styles.meta}>{meta}</AppText> : null}
      </View>
      {reasons.slice(0, maxReasons).map((reason) => (
        <AppText key={reason} style={styles.reason}>
          {`• ${reason}`}
        </AppText>
      ))}
      <View style={styles.pillRow} accessibilityLabel={effect}>
        {swap ? <AppText style={styles.kicker}>WHOLE SWAP</AppText> : null}
        {pills.map((pill) => (
          <ToneBadge key={pill.label} label={pill.label} color={pill.color} />
        ))}
      </View>
    </View>
  );
}

function effectPills(effect: DropPlayer['effect'], colors: ThemeColors): { label: string; color: string }[] {
  const pills: { label: string; color: string }[] = [];
  const pts = effect.lineup_points_ros;
  if (Math.abs(pts) < 0.5) pills.push({ label: 'No lineup change', color: colors.textTertiary });
  else
    pills.push({
      label: `${pts > 0 ? '+' : '-'}${Math.abs(Math.round(pts))} pts / ${effect.weeks} wks`,
      color: pts > 0 ? colors.success : colors.danger,
    });
  const value = valueEffectText(effect);
  if (value) pills.push({ label: value, color: effect.value_delta > 0 ? colors.success : colors.danger });
  return pills;
}

type ReasonIcon = keyof typeof Ionicons.glyphMap;
function reasonIcon(reason: string): ReasonIcon {
  const r = reason.toLowerCase();
  if (/injur|\bir\b|out for|suspend/.test(r)) return 'medkit-outline';
  if (/never start|bench|backup|depth|rotation|string|roster|snap|usage|role/.test(r)) return 'list-outline';
  if (/\bage\b|\bold\b|years?|decline|aging/.test(r)) return 'time-outline';
  return 'information-circle-outline';
}

function SwapTile({ side, player, name, playerId, position, team }: { side: 'add' | 'drop'; player?: DropPlayer; name: string; playerId: string; position: string; team?: string }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const color = side === 'add' ? colors.success : colors.danger;
  const label = side === 'add' ? 'ADD' : player?.action === 'move_to_ir' ? 'TO IR' : 'DROP';
  return (
    <View style={[styles.tile, { borderColor: `${color}8C`, backgroundColor: `${color}14` }]} testID={`swap-${side}`}>
      <ToneBadge label={label} color={color} size="xs" />
      <PlayerAvatar playerId={playerId} size={44} />
      <AppText style={[styles.playerName, { textAlign: 'center' }]}>{name}</AppText>
      <View style={styles.pillRow}>
        <PositionBadge position={position} />
        {team ? <AppText style={styles.meta}>{`${team}${player?.age ? ` · ${Math.round(player.age)}` : ''}`}</AppText> : null}
      </View>
    </View>
  );
}

/** ADD tile, arrow, DROP tile; effect pills; two icon reason chips; alternative cuts as avatar chips that swap the selection. */
function SwapBody({ suggestion, drop, alternatives }: { suggestion: DropSuggestion; drop: DropPlayer; alternatives: DropPlayer[] }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [showWhy, setShowWhy] = useState(false);
  const pool = [drop, ...alternatives];
  const selected = pool.find((p) => p.player_id === selectedId) ?? drop;
  const others = pool.filter((p) => p.player_id !== selected.player_id);
  const effectSentence = [lineupEffectText(selected.effect), valueEffectText(selected.effect)].filter(Boolean).join(' · ');
  return (
    <View style={{ gap: spacing.sm }}>
      <AppText
        accessibilityLabel={`Add ${suggestion.add.name}, ${selected.action === 'move_to_ir' ? 'move' : 'drop'} ${selected.name}${selected.action === 'move_to_ir' ? ' to IR' : ''}`}
        style={{ height: 0, opacity: 0 }}
      >
        {' '}
      </AppText>
      <View style={styles.swapRow}>
        <SwapTile side="add" name={suggestion.add.name} playerId={suggestion.add.player_id} position={suggestion.add.position} />
        <Ionicons name="swap-horizontal" size={22} color={colors.textTertiary} />
        <SwapTile side="drop" player={selected} name={selected.name} playerId={selected.player_id} position={selected.position} team={selected.team} />
      </View>
      <View style={styles.pillRow} testID="swap-effect" accessibilityLabel={`Whole swap: ${effectSentence}`}>
        <AppText style={styles.kicker}>SWAP</AppText>
        {effectPills(selected.effect, colors).map((pill) => (
          <ToneBadge key={pill.label} label={pill.label} color={pill.color} />
        ))}
      </View>
      {selected.reasons.length > 0 ? (
        <View style={styles.pillRow} testID="swap-reasons">
          {selected.reasons.slice(0, 2).map((reason) => (
            <View key={reason} style={styles.reasonChip}>
              <Ionicons name={reasonIcon(reason)} size={12} color={colors.textSecondary} />
              <AppText style={styles.reasonChipText} numberOfLines={1}>
                {reason}
              </AppText>
            </View>
          ))}
        </View>
      ) : null}
      <TouchableOpacity onPress={() => setShowWhy((v) => !v)} accessibilityRole="button" accessibilityState={{ expanded: showWhy }} style={{ minHeight: 32, justifyContent: 'center' }}>
        <AppText style={[styles.meta, { color: colors.accent, fontWeight: '700' }]}>{showWhy ? 'Hide details' : 'Why this cut'}</AppText>
      </TouchableOpacity>
      {showWhy ? <DropPlayerLine player={selected} lead={selected === drop ? 'Best cut:' : 'Drop'} swap maxReasons={6} /> : null}
      {others.length > 0 ? (
        <View style={styles.alts} testID="swap-alternatives">
          <AppText style={styles.kicker}>OR CUT INSTEAD</AppText>
          <View style={styles.pillRow}>
            {others.map((alt) => (
              <TouchableOpacity
                key={alt.player_id}
                style={styles.altChip}
                onPress={() => setSelectedId(alt.player_id === drop.player_id ? null : alt.player_id)}
                accessibilityRole="button"
                accessibilityLabel={`Cut ${alt.name} instead`}
              >
                <PlayerAvatar playerId={alt.player_id} size={28} />
                <AppText style={[styles.meta, { color: colors.textPrimary, fontWeight: '700', maxWidth: 110 }]} numberOfLines={1}>
                  {alt.name}
                </AppText>
                <PositionBadge position={alt.position} />
              </TouchableOpacity>
            ))}
          </View>
        </View>
      ) : null}
    </View>
  );
}

function useBadge(suggestion: DropSuggestion) {
  const { colors } = useThemeMode();
  const { drop } = suggestion;
  return drop != null
    ? { label: dropActionLabel(drop), color: colors.danger }
    : suggestion.no_good_drop
      ? { label: 'No good drop', color: colors.warning }
      : suggestion.drop_required === false
        ? { label: 'Spot open', color: colors.success }
        : { label: 'Roster', color: colors.textTertiary };
}

/** List rows: one line (badge + full player name), details one tap away. The top target shows the full block. */
function CompactSuggestedDrop({ suggestion }: { suggestion: DropSuggestion }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [open, setOpen] = useState(false);
  const badge = useBadge(suggestion);
  const { drop, alternatives } = suggestion;
  const label = drop ? drop.name : suggestion.drop_required === false ? 'No drop needed' : '';
  return (
    <View testID="suggested-drop-compact" style={styles.compactWrap}>
      <TouchableOpacity
        style={styles.compactRow}
        onPress={() => setOpen((v) => !v)}
        accessibilityRole="button"
        accessibilityState={{ expanded: open }}
        accessibilityLabel={`${badge.label} ${label}`}
      >
        <View style={[styles.badge, { borderColor: `${badge.color}70`, backgroundColor: `${badge.color}1A` }]}>
          <AppText style={[styles.badgeText, { color: badge.color }]}>{badge.label}</AppText>
        </View>
        {drop ? <PlayerAvatar playerId={drop.player_id} size={24} /> : null}
        <AppText style={[styles.playerName, { flex: 1 }]}>{label}</AppText>
        {drop ? <PositionBadge position={drop.position} /> : null}
        <AppText style={[styles.meta, { color: colors.accent, fontWeight: '700' }]}>{open ? 'Hide' : 'Why'}</AppText>
      </TouchableOpacity>
      {open ? (
        <View style={styles.compactDetails} testID="suggested-drop-details">
          {drop ? (
            <SwapBody suggestion={suggestion} drop={drop} alternatives={alternatives} />
          ) : (
            <>
              <AppText style={styles.body}>{suggestion.why}</AppText>
              {suggestion.no_good_drop && suggestion.cheapest ? <DropPlayerLine player={suggestion.cheapest} lead="Cheapest cut:" /> : null}
            </>
          )}
        </View>
      ) : null}
    </View>
  );
}

export function SuggestedDrop({ suggestion, compact = false }: { suggestion: DropSuggestion; compact?: boolean }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const badge = useBadge(suggestion);
  if (compact) return <CompactSuggestedDrop suggestion={suggestion} />;
  const { drop, alternatives } = suggestion;
  return (
    <View style={styles.box} testID="suggested-drop">
      <View style={styles.headRow}>
        <AppText style={styles.kicker}>ROSTER MOVE</AppText>
        <View style={[styles.badge, { borderColor: `${badge.color}70`, backgroundColor: `${badge.color}1A` }]}>
          <AppText style={[styles.badgeText, { color: badge.color }]}>{badge.label}</AppText>
        </View>
      </View>
      {drop ? (
        <SwapBody suggestion={suggestion} drop={drop} alternatives={alternatives} />
      ) : (
        <>
          <AppText style={styles.body}>{suggestion.why}</AppText>
          {suggestion.no_good_drop && suggestion.cheapest ? (
            <DropPlayerLine player={suggestion.cheapest} lead="Cheapest cut:" />
          ) : null}
        </>
      )}
    </View>
  );
}

export function DroppablePlayersSection({ data }: { data: DroppablePlayers | null | undefined }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  if (!data) return null;
  return (
    <View testID="droppable-players">
      {data.players.length === 0 ? (
        <AppText style={styles.body}>
          {`Nobody on your roster is a free cut right now${
            data.protected_count > 0 ? ` (${data.protected_count} players are starters, high-value, needed depth or upside)` : ''
          }. If you add someone, their roster move shows the cheapest cut, or says there is no good one.`}
        </AppText>
      ) : (
        <View style={styles.listBox}>
          {data.players.map((player) => (
            <View key={player.player_id} style={{ gap: 2 }}>
              <DropPlayerLine player={player} lead={player.action === 'move_to_ir' ? 'Move to IR:' : undefined} />
              {player.named_for && player.named_for.length > 0 ? (
                <AppText style={[styles.meta, { color: colors.accent, fontWeight: '700' }]}>
                  {`The cut when you add ${player.named_for.slice(0, 3).join(', ')}${
                    player.named_for.length > 3 ? ` +${player.named_for.length - 3}` : ''
                  }`}
                </AppText>
              ) : null}
            </View>
          ))}
          {data.locked_count > 0 ? <AppText style={styles.lock}>{`+${data.locked_count} more with Pro`}</AppText> : null}
        </View>
      )}
      <ScreenInfoNote
        label="How drops are chosen"
        text="Lowest cost to your team first: players who never start, cost your lineup nothing if cut and have little value. Never suggested: starters, high-value assets, depth you need for byes and injuries, young upside for your team direction, hot players, and anyone you marked untouchable."
      />
    </View>
  );
}

/** "Roster full: you'd have to drop N" for a trade that overfills the roster (Analyzer verdict and Hub/Finder cards). */
export function RosterOverflowNote({ overflow, compact = false }: { overflow: RosterOverflow; compact?: boolean }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const effect = overflow.effect ? [lineupEffectText(overflow.effect), valueEffectText(overflow.effect)].filter(Boolean).join(' · ') : '';
  return (
    <View style={[styles.box, { borderColor: colors.warning }]} testID="roster-overflow">
      <View style={styles.headRow}>
        <AppText style={[styles.kicker, { color: colors.warning }]}>ROSTER FULL</AppText>
        <View style={[styles.badge, { borderColor: `${colors.warning}70`, backgroundColor: `${colors.warning}1A` }]}>
          <AppText style={[styles.badgeText, { color: colors.warning }]}>{`${overflow.active_after}/${overflow.active_limit}`}</AppText>
        </View>
      </View>
      <AppText style={styles.headline}>{overflowHeadline(overflow)}</AppText>
      {overflow.unavailable
        ? null
        : overflow.drops.map((drop) => <DropPlayerLine key={drop.player_id} player={drop} maxReasons={compact ? 1 : 2} />)}
      {!overflow.unavailable && effect ? <AppText style={styles.effect}>{`Cost of the cuts, already in this result: ${effect}`}</AppText> : null}
    </View>
  );
}

/** The numbers behind the Team need stat, per position (opens from the info note). */
export function needsBreakdownText(needs: NeedsModel): string {
  const lines = needs.positions.map(
    (p) =>
      `${p.position} (${needTierLabel(p.tier)}): weakest slot ${weakestSlotText(p)}; best free agent: ${upgradeText(p)}; depth ${p.healthy_count}/${p.required_depth}.${
        p.reasons.length ? ` ${p.reasons.join('; ')}.` : ''
      }`,
  );
  return `${lines.join('\n\n')}\n\nRanks compare each starter slot with the same slot on every team, using expected lineup points. The free agent figure is the lineup points per week the best available player would add. Depth is healthy players vs starters plus one bye/injury cover.`;
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    compactWrap: { marginTop: spacing.xs, gap: spacing.xs, paddingHorizontal: spacing.md, paddingVertical: spacing.xs, borderRadius: radii.md, borderWidth: StyleSheet.hairlineWidth, borderColor: colors.border },
    compactRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, minHeight: 36 },
    compactDetails: { gap: spacing.xs, paddingLeft: spacing.xs },
    box: {
      marginTop: spacing.sm,
      padding: spacing.sm,
      gap: spacing.xs,
      borderRadius: radii.md,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: colors.border,
    },
    headRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
    kicker: { fontSize: 10, fontWeight: '800', letterSpacing: 0.6, color: colors.textTertiary },
    badge: { borderRadius: radii.pill, borderWidth: 1, paddingHorizontal: spacing.sm, paddingVertical: 2 },
    badgeText: { fontSize: 11, fontWeight: '700' },
    headline: { fontSize: 13, fontWeight: '700', color: colors.textPrimary },
    body: { fontSize: 12, lineHeight: 17, color: colors.textSecondary },
    playerLine: { gap: 4 },
    nameRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs, flexWrap: 'wrap' },
    pillRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs, flexWrap: 'wrap' },
    swapRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs },
    tile: { flex: 1, alignItems: 'center', gap: 4, padding: spacing.sm, borderRadius: radii.md, borderWidth: 1 },
    reasonChip: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: 4,
      maxWidth: '100%',
      paddingHorizontal: spacing.sm,
      paddingVertical: 2,
      borderRadius: radii.pill,
      backgroundColor: colors.accentSoft,
    },
    reasonChipText: { flexShrink: 1, fontSize: 12, fontWeight: '600', color: colors.textSecondary },
    altChip: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: 6,
      paddingRight: spacing.sm,
      paddingLeft: 2,
      paddingVertical: 2,
      minHeight: 36,
      borderRadius: radii.pill,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: colors.border,
    },
    playerName: { fontSize: 13, fontWeight: '700', color: colors.textPrimary },
    meta: { fontSize: 11, fontWeight: '600', color: colors.textTertiary },
    reason: { fontSize: 12, lineHeight: 16, color: colors.textSecondary, paddingLeft: spacing.sm },
    effect: { fontSize: 11, color: colors.textTertiary },
    alts: { gap: spacing.xs, paddingTop: spacing.xs, borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.border },
    listBox: { gap: spacing.md, padding: spacing.md, borderRadius: radii.md, borderWidth: StyleSheet.hairlineWidth, borderColor: colors.border },
    lock: { fontSize: 12, fontWeight: '700', color: colors.premium },
  });
}
