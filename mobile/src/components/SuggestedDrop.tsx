import React, { useMemo } from 'react';
import { StyleSheet, View } from 'react-native';

import AppText from './AppText';
import ScreenInfoNote from './ScreenInfoNote';
import { useThemeMode } from '../context/ThemeModeContext';
import type { DropPlayer, DropSuggestion, DroppablePlayers, NeedsModel } from '../lib/api';
import {
  dropActionLabel,
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

/** `compact` (list rows): the pick with its top reason and the alternatives' names; the top card shows everything. */
export function SuggestedDrop({ suggestion, compact = false }: { suggestion: DropSuggestion; compact?: boolean }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const { drop, alternatives } = suggestion;
  const badge =
    drop != null
      ? { label: dropActionLabel(drop), color: colors.danger }
      : suggestion.no_good_drop
        ? { label: 'No good drop', color: colors.warning }
        : suggestion.drop_required === false
          ? { label: 'Spot open', color: colors.success }
          : { label: 'Roster', color: colors.textTertiary };
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
          <DropPlayerLine player={drop} maxReasons={compact ? 1 : 3} />
          {compact && alternatives.length > 0 ? (
            <AppText style={styles.effect}>{`Or: ${alternatives.map((alt) => alt.name).join(', ')}`}</AppText>
          ) : null}
          {!compact && alternatives.length > 0 ? (
            <View style={styles.alts}>
              <AppText style={styles.kicker}>OR</AppText>
              {alternatives.map((alt) => (
                <DropPlayerLine key={alt.player_id} player={alt} />
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
          {`No free drops right now: nobody is both useless to your lineup and low in value${
            data.protected_count > 0 ? ` (${data.protected_count} players are starters, high-value, needed depth or upside)` : ''
          }. When you add someone, the roster move above picks the cheapest cut.`}
        </AppText>
      ) : (
        <View style={styles.listBox}>
          {data.players.map((player) => (
            <DropPlayerLine
              key={player.player_id}
              player={player}
              lead={player.action === 'move_to_ir' ? 'Move to IR:' : undefined}
            />
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
