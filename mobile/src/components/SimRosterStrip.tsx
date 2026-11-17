import React, { useMemo, useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import AppText from './AppText';
import PlayerAvatarSlot from './PlayerAvatarSlot';
import PositionBadge from './PositionBadge';
import { Collapse } from './Presence';
import { useThemeMode } from '../context/ThemeModeContext';
import { simDraftRosterStrip } from '../lib/simDraft';
import { simHeadshotId, type SimGamePlayer, type SimSlot } from '../lib/simGame';
import { positionColor, spacing, type ThemeColors } from '../theme';

const AVATAR = 28;

/**
 * "Your roster" inside the draft clock: the league's starting slots in order, filled slots show the drafted player (tap
 * opens him), empty strict slots are dashed outlines in the warning colour (the same holes the header's "need RB/TE"
 * names, one source: `simDraftRosterStrip`), plus "Bench n/m". Tapping the strip expands the full roster grouped by
 * position; collapsed by default (compact, tap to expand). Used by the startup and rookie drafts. Web twin: SimRosterStrip.tsx.
 */
export function SimRosterStrip({ roster, slots, rosterLimit, bench, onOpen }: { roster: readonly SimGamePlayer[]; slots: readonly SimSlot[]; rosterLimit: number; bench?: number | null; onOpen: (player: SimGamePlayer) => void }) {
  const { colors, isDark } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [open, setOpen] = useState(false);
  const strip = simDraftRosterStrip(roster, slots, rosterLimit, bench);
  if (strip.slots.length === 0) return null;
  const needs = [...new Set(strip.slots.filter((c) => c.need).map((c) => c.label))];
  const toggle = () => setOpen((v) => !v);
  return (
    <View style={styles.wrap} testID="roster-strip">
      <Pressable onPress={toggle} accessibilityRole="button" accessibilityState={{ expanded: open }} accessibilityLabel={`Your roster, bench ${strip.bench.have} of ${strip.bench.max}`} style={styles.head} testID="roster-strip-toggle">
        <AppText style={styles.kicker}>Your roster</AppText>
        <View style={styles.needs} testID="roster-strip-needs" accessibilityLabel={`Needs: ${needs.join(", ")}`}>
          {needs.slice(0, 3).map((pos) => (
            <View key={pos} style={[styles.needChip, { borderColor: colors.warning }]}>
              <AppText style={[styles.needText, { color: colors.warning }]}>{pos}</AppText>
            </View>
          ))}
          {needs.length > 3 ? <AppText style={[styles.needText, { color: colors.warning }]}>{`+${needs.length - 3}`}</AppText> : null}
        </View>
        <AppText style={styles.bench} testID="roster-strip-bench">{`Bench ${strip.bench.have}/${strip.bench.max} ${open ? '▴' : '▾'}`}</AppText>
      </Pressable>
      {/* ONE fixed grid: every slot is the same size with the label at the same height, filled or empty, in lineup order on one row. */}
      <View style={styles.slots} testID="roster-strip-slots">
        {strip.slots.map((cell) =>
          cell.player ? (
            <View key={cell.key} style={styles.cell} accessibilityLabel={`${cell.label}: ${cell.player.name}, ${cell.player.pos}`} testID="roster-slot-filled">
              <PlayerAvatarSlot player={{ id: cell.player.id, name: cell.player.name, position: cell.player.pos, team: cell.player.team ?? null, headshotId: simHeadshotId(cell.player) }} tier="dense" onOpen={() => onOpen(cell.player!)} />
              <AppText style={[styles.slotLabel, { color: positionColor(cell.player.pos, isDark, colors.textSecondary) }]}>{cell.label}</AppText>
            </View>
          ) : (
            <Pressable key={cell.key} onPress={toggle} accessibilityRole="button" accessibilityLabel={`${cell.label} slot empty${cell.need ? ', you need one' : ''}`} style={styles.cell} testID="roster-slot-empty">
              <View style={[styles.empty, { borderColor: colors.warning }]}>
                <AppText style={[styles.plus, { color: colors.warning }]}>+</AppText>
              </View>
              <AppText style={[styles.slotLabel, { color: colors.warning }]}>{cell.label}</AppText>
            </Pressable>
          ),
        )}
      </View>
      <Collapse open={open}>
        <>
          <View style={styles.full} testID="roster-strip-full">
            {strip.groups.map((g) => (
              <View key={g.pos} style={styles.group}>
                <AppText style={[styles.groupHead, { color: g.starters > 0 && g.have < g.starters ? colors.warning : colors.textTertiary }]}>{`${g.pos} ${g.have}/${g.starters}`}</AppText>
                {g.players.length === 0 ? (
                  <AppText style={styles.none}>None yet</AppText>
                ) : (
                  g.players.map((pl) => (
                    <View key={pl.id} style={styles.line} testID="roster-strip-player">
                      <PlayerAvatarSlot player={{ id: pl.id, name: pl.name, position: pl.pos, team: pl.team ?? null, headshotId: simHeadshotId(pl) }} tier="dense" onOpen={() => onOpen(pl)} />
                      <AppText style={styles.name}>{pl.name}</AppText>
                      <PositionBadge position={pl.pos} />
                    </View>
                  ))
                )}
              </View>
            ))}
          </View>
        </>
      </Collapse>
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    wrap: { gap: 4 },
    head: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, minHeight: 44 },
    needs: { flex: 1, flexDirection: 'row', flexWrap: 'wrap', gap: 4 },
    needChip: { minHeight: 20, paddingHorizontal: 6, borderRadius: 999, borderWidth: 1, justifyContent: 'center' },
    needText: { fontSize: 12, fontWeight: '800' },
    kicker: { fontSize: 12, fontWeight: '800', letterSpacing: 0.6, textTransform: 'uppercase', color: colors.textTertiary },
    bench: { fontSize: 12, fontWeight: '700', color: colors.textTertiary },
    slots: { flexDirection: 'row', columnGap: 4 },
    cell: { flex: 1, minWidth: 0, minHeight: 44, alignItems: 'center', gap: 2 },
    empty: { width: AVATAR, height: AVATAR, borderRadius: AVATAR / 2, borderWidth: 1.5, borderStyle: 'dashed', alignItems: 'center', justifyContent: 'center' },
    plus: { fontSize: 12, fontWeight: '800' },
    slotLabel: { fontSize: 12, fontWeight: '800' },
    full: { gap: spacing.sm },
    group: { gap: 4 },
    groupHead: { fontSize: 12, fontWeight: '800' },
    none: { fontSize: 12, color: colors.textTertiary },
    line: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, minHeight: 44 },
    name: { flex: 1, minWidth: 0, fontSize: 14, fontWeight: '700', color: colors.textPrimary },
  });
}
