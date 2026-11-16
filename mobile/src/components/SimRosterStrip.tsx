import React, { useMemo, useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import AppText from './AppText';
import PlayerAvatar from './PlayerAvatar';
import PositionBadge from './PositionBadge';
import { MotionIn } from './Motion';
import { useThemeMode } from '../context/ThemeModeContext';
import { simDraftRosterStrip } from '../lib/simDraft';
import { simHeadshotId, type SimGamePlayer, type SimSlot } from '../lib/simGame';
import { spacing, type ThemeColors } from '../theme';

const AVATAR = 28;

/**
 * "Your roster" inside the draft clock: the league's starting slots in order, filled slots show the drafted player (tap
 * opens him), empty strict slots are dashed outlines in the warning colour (the same holes the header's "need RB/TE"
 * names, one source: `simDraftRosterStrip`), plus "Bench n/m". Tapping the strip expands the full roster grouped by
 * position; collapsed by default (compact, tap to expand). Used by the startup and rookie drafts. Web twin: SimRosterStrip.tsx.
 */
export function SimRosterStrip({ roster, slots, rosterLimit, bench, onOpen }: { roster: readonly SimGamePlayer[]; slots: readonly SimSlot[]; rosterLimit: number; bench?: number | null; onOpen: (player: SimGamePlayer) => void }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [open, setOpen] = useState(false);
  const strip = simDraftRosterStrip(roster, slots, rosterLimit, bench);
  if (strip.slots.length === 0) return null;
  const toggle = () => setOpen((v) => !v);
  return (
    <View style={styles.wrap} testID="roster-strip">
      <Pressable onPress={toggle} accessibilityRole="button" accessibilityState={{ expanded: open }} accessibilityLabel={`Your roster, bench ${strip.bench.have} of ${strip.bench.max}`} style={styles.head} testID="roster-strip-toggle">
        <AppText style={styles.kicker}>Your roster</AppText>
        <AppText style={styles.bench} testID="roster-strip-bench">{`Bench ${strip.bench.have}/${strip.bench.max} ${open ? '▴' : '▾'}`}</AppText>
      </Pressable>
      <View style={styles.slots} testID="roster-strip-slots">
        {strip.slots.map((cell) =>
          cell.player ? (
            <Pressable key={cell.key} onPress={() => onOpen(cell.player!)} accessibilityRole="button" accessibilityLabel={`${cell.label}: ${cell.player.name}, ${cell.player.pos}. Open player`} style={styles.cell} testID="roster-slot-filled">
              <PlayerAvatar playerId={simHeadshotId(cell.player)} size={AVATAR} fallbackLabel={cell.player.name.trim().slice(0, 1)} />
              <PositionBadge position={cell.player.pos} />
            </Pressable>
          ) : (
            <Pressable key={cell.key} onPress={toggle} accessibilityRole="button" accessibilityLabel={`${cell.label} slot empty${cell.need ? ', you need one' : ''}`} style={styles.cell} testID="roster-slot-empty">
              <View style={[styles.empty, { borderColor: cell.need ? colors.warning : colors.border }]}>
                <AppText style={[styles.plus, { color: cell.need ? colors.warning : colors.textTertiary }]}>+</AppText>
              </View>
              <AppText style={[styles.slotLabel, { color: cell.need ? colors.warning : colors.textTertiary }]}>{cell.label}</AppText>
            </Pressable>
          ),
        )}
      </View>
      {open ? (
        <MotionIn>
          <View style={styles.full} testID="roster-strip-full">
            {strip.groups.map((g) => (
              <View key={g.pos} style={styles.group}>
                <AppText style={[styles.groupHead, { color: g.starters > 0 && g.have < g.starters ? colors.warning : colors.textTertiary }]}>{`${g.pos} ${g.have}/${g.starters}`}</AppText>
                {g.players.length === 0 ? (
                  <AppText style={styles.none}>None yet</AppText>
                ) : (
                  g.players.map((pl) => (
                    <Pressable key={pl.id} onPress={() => onOpen(pl)} accessibilityRole="button" accessibilityLabel={`${pl.name}, ${pl.pos}. Open player`} style={styles.line} testID="roster-strip-player">
                      <PlayerAvatar playerId={simHeadshotId(pl)} size={AVATAR} fallbackLabel={pl.name.trim().slice(0, 1)} />
                      <AppText style={styles.name}>{pl.name}</AppText>
                      <PositionBadge position={pl.pos} />
                    </Pressable>
                  ))
                )}
              </View>
            ))}
          </View>
        </MotionIn>
      ) : null}
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    wrap: { gap: 4 },
    head: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', minHeight: 44 },
    kicker: { fontSize: 12, fontWeight: '800', letterSpacing: 0.6, textTransform: 'uppercase', color: colors.textTertiary },
    bench: { fontSize: 12, fontWeight: '700', color: colors.textTertiary },
    slots: { flexDirection: 'row', flexWrap: 'wrap', columnGap: spacing.sm, rowGap: 4 },
    cell: { width: 36, minHeight: 44, alignItems: 'center', gap: 2 },
    empty: { width: AVATAR, height: AVATAR, borderRadius: AVATAR / 2, borderWidth: 1.5, borderStyle: 'dashed', alignItems: 'center', justifyContent: 'center' },
    plus: { fontSize: 12, fontWeight: '800' },
    slotLabel: { fontSize: 10, fontWeight: '800' },
    full: { gap: spacing.sm },
    group: { gap: 4 },
    groupHead: { fontSize: 12, fontWeight: '800' },
    none: { fontSize: 12, color: colors.textTertiary },
    line: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, minHeight: 44 },
    name: { flex: 1, minWidth: 0, fontSize: 14, fontWeight: '700', color: colors.textPrimary },
  });
}
