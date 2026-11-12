import React, { useMemo } from 'react';
import { Pressable, ScrollView, StyleSheet, View } from 'react-native';

import AppText from './AppText';
import EmptyState from './EmptyState';
import { SimDraftEmblem } from './SimDraftHero';
import { useThemeMode } from '../context/ThemeModeContext';
import { simDraftBoardGrid } from '../lib/simDraft';
import type { SimDraftState, SimGamePlayer } from '../lib/simGame';
import { positionColor, spacing, type ThemeColors } from '../theme';

const COL = 76;
const ROUND_W = 32;

/**
 * Rounds x teams draft board. Picks are tinted by position, your column is
 * outlined and the pick on the clock has an accent ring. The grid scrolls in
 * both directions inside its own box; the screen itself never scrolls sideways.
 */
export function SimDraftGrid({ draft, teams, onOpen }: { draft: SimDraftState; teams: number; onOpen: (player: SimGamePlayer) => void }) {
  const { colors, isDark } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const grid = useMemo(() => simDraftBoardGrid(draft, teams), [draft, teams]);
  if (grid.teams.length === 0) return <EmptyState icon="grid-outline" title="No board yet" subtitle="The draft grid shows up once teams are set." />;
  return (
    <ScrollView horizontal nestedScrollEnabled style={styles.box} testID="draft-grid-scroll">
      <View>
        <View style={styles.row}>
          <View style={{ width: ROUND_W }} />
          {grid.teams.map((t) => (
            <View key={t.team_id} style={[styles.head, t.is_you && { borderBottomColor: colors.accent, borderBottomWidth: 3 }]}>
              <SimDraftEmblem name={t.name} you={t.is_you} />
              <AppText style={[styles.headName, t.is_you && { color: colors.accent }]} numberOfLines={1}>
                {t.is_you ? 'You' : t.name}
              </AppText>
            </View>
          ))}
        </View>
        {grid.rows.map((row, i) => (
          <View key={i} style={styles.row}>
            <View style={[styles.round]}>
              <AppText style={styles.roundText}>R{i + 1}</AppText>
            </View>
            {row.map((cell, c) => {
              const you = grid.teams[c].is_you;
              const clock = !cell.pick && cell.pickNo === draft.pick_no && draft.status === 'in_progress';
              const tint = cell.pick ? positionColor(cell.pick.player.pos, isDark, colors.borderStrong) : null;
              return (
                <View key={cell.teamId} style={[styles.cellWrap, you && { backgroundColor: colors.accentMuted }]}>
                  {cell.pick ? (
                    <Pressable
                      onPress={() => onOpen(cell.pick!.player)}
                      accessibilityRole="button"
                      accessibilityLabel={`Pick ${cell.pick.pick_no}: ${cell.pick.player.name}, ${cell.pick.player.pos}`}
                      style={[styles.cell, { borderLeftWidth: 3, borderLeftColor: tint ?? colors.borderStrong, backgroundColor: colors.glass }]}
                    >
                      <AppText style={styles.cellName} numberOfLines={1}>
                        {cell.pick.player.name.split(/\s+/).slice(-1)[0]}
                      </AppText>
                      <AppText style={styles.cellMeta}>
                        {cell.pick.player.pos} · #{cell.pick.pick_no}
                      </AppText>
                    </Pressable>
                  ) : (
                    <View style={[styles.cell, styles.empty, clock && { borderColor: colors.accent, borderWidth: 2, borderStyle: 'solid' }]}>
                      <AppText style={[styles.cellMeta, clock && { color: colors.accent }]}>{cell.pickNo ?? ''}</AppText>
                    </View>
                  )}
                </View>
              );
            })}
          </View>
        ))}
      </View>
    </ScrollView>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    box: { borderWidth: StyleSheet.hairlineWidth, borderColor: colors.border, borderRadius: 14 },
    row: { flexDirection: 'row' },
    head: { width: COL, alignItems: 'center', gap: 2, paddingVertical: spacing.xs, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border },
    headName: { fontSize: 10, fontWeight: '700', color: colors.textTertiary, width: COL - 8, textAlign: 'center' },
    round: { width: ROUND_W, alignItems: 'center', justifyContent: 'center' },
    roundText: { fontSize: 10, fontWeight: '800', color: colors.textTertiary },
    cellWrap: { width: COL, padding: 2 },
    cell: { height: 44, borderRadius: 8, justifyContent: 'center', paddingHorizontal: 4 },
    empty: { alignItems: 'center', borderWidth: StyleSheet.hairlineWidth, borderColor: colors.border, borderStyle: 'dashed' },
    cellName: { fontSize: 11, fontWeight: '700', color: colors.textPrimary },
    cellMeta: { fontSize: 9, color: colors.textTertiary },
  });
}
