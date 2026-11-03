import React, { useMemo, useState } from 'react';
import { StyleSheet, TouchableOpacity, View } from 'react-native';

import AppText from './AppText';
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

function DropPlayerLine({ player, lead, maxReasons = 3 }: { player: DropPlayer; lead?: string; maxReasons?: number }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const effect = [lineupEffectText(player.effect), valueEffectText(player.effect)].filter(Boolean).join(' · ');
  const meta = [player.position, player.team, player.age ? String(Math.round(player.age)) : ''].filter(Boolean).join(' · ');
  return (
    <View style={styles.playerLine}>
      <AppText style={styles.playerName}>
        {lead ? `${lead} ` : ''}
        {player.name} <AppText style={styles.meta}>{meta}</AppText>
      </AppText>
      {player.reasons.slice(0, maxReasons).map((reason) => (
        <AppText key={reason} style={styles.reason}>
          {`• ${reason}`}
        </AppText>
      ))}
      {effect ? <AppText style={styles.effect}>{effect}</AppText> : null}
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
  const label = drop ? `${drop.name} · ${drop.position}` : suggestion.drop_required === false ? 'No drop needed' : '';
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
        <AppText style={[styles.playerName, { flex: 1 }]}>{label}</AppText>
        <AppText style={[styles.meta, { color: colors.accent, fontWeight: '700' }]}>{open ? 'Hide' : 'Why'}</AppText>
      </TouchableOpacity>
      {open ? (
        <View style={styles.compactDetails} testID="suggested-drop-details">
          <AppText style={styles.body}>
            {drop
              ? `Add ${suggestion.add.name}, ${drop.action === 'move_to_ir' ? 'move' : 'drop'} ${drop.name}${drop.action === 'move_to_ir' ? ' to IR' : ''}`
              : suggestion.why}
          </AppText>
          {drop ? (
            <DropPlayerLine player={drop} />
          ) : suggestion.no_good_drop && suggestion.cheapest ? (
            <DropPlayerLine player={suggestion.cheapest} lead="Cheapest cut:" />
          ) : null}
          {alternatives.length > 0 ? <AppText style={styles.effect}>{`Or: ${alternatives.map((alt) => alt.name).join(', ')}`}</AppText> : null}
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
        <>
          <AppText style={styles.headline}>
            {`Add ${suggestion.add.name}, ${drop.action === 'move_to_ir' ? 'move' : 'drop'} ${drop.name}${
              drop.action === 'move_to_ir' ? ' to IR' : ''
            }`}
          </AppText>
          <DropPlayerLine player={drop} />
          {alternatives.length > 0 ? (
            <View style={styles.alts}>
              <AppText style={styles.kicker}>OR</AppText>
              {alternatives.map((alt) => (
                <DropPlayerLine key={alt.player_id} player={alt} maxReasons={1} />
              ))}
            </View>
          ) : null}
        </>
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
          {data.locked_count > 0 ? <AppText style={styles.lock}>{`+${data.locked_count} more with Premium`}</AppText> : null}
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
    compactWrap: { marginTop: spacing.xs, gap: spacing.xs },
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
    playerLine: { gap: 2 },
    playerName: { fontSize: 13, fontWeight: '700', color: colors.textPrimary },
    meta: { fontSize: 11, fontWeight: '600', color: colors.textTertiary },
    reason: { fontSize: 12, lineHeight: 16, color: colors.textSecondary, paddingLeft: spacing.sm },
    effect: { fontSize: 11, color: colors.textTertiary },
    alts: { gap: spacing.xs, paddingTop: spacing.xs, borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.border },
    listBox: { gap: spacing.md, padding: spacing.md, borderRadius: radii.md, borderWidth: StyleSheet.hairlineWidth, borderColor: colors.border },
    lock: { fontSize: 12, fontWeight: '700', color: colors.premium },
  });
}
