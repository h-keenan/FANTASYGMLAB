import React, { useMemo, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, View } from 'react-native';

import AppText from './AppText';
import CompactModule from './CompactModule';
import { Sheet } from './Sheet';
import { SimDraftGrid } from './SimDraftGrid';
import { useThemeMode } from '../context/ThemeModeContext';
import { simDraftMiniBoard, simDraftMiniWindow, simDraftPickChip, simDraftProgress, simDraftRecentPicks } from '../lib/simDraft';
import type { SimDraftState, SimGamePlayer } from '../lib/simGame';
import { positionColor, radii, spacing, type ThemeColors } from '../theme';

/**
 * "Who has been drafted", always on the draft page (not behind a tab): a strip of the latest picks and a mini board
 * (rounds x teams of tiny position-coloured cells, your column outlined, the pick on the clock ringed). The mini
 * board shows the rounds around the clock; "Full board" opens the whole grid in a sheet. Web twin: SimDraftOverview.tsx.
 */
export function SimDraftOverview({ draft, teams, onOpen }: { draft: SimDraftState; teams: number; onOpen: (player: SimGamePlayer) => void }) {
  const { colors, isDark } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [full, setFull] = useState(false);
  const recent = simDraftRecentPicks(draft.picks, 8);
  const progress = simDraftProgress(draft, teams);
  const mini = useMemo(() => simDraftMiniBoard(draft, teams), [draft, teams]);
  const win = simDraftMiniWindow(mini.rows, progress.round);
  const mine = (draft.picks ?? []).filter((p) => draft.teams?.find((t) => t.team_id === p.team_id)?.is_you).length;
  const last = recent[0];
  return (
    <View style={styles.wrap} testID="draft-overview">
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.strip} accessibilityLabel="Recent picks" testID="recent-picks">
        {recent.length === 0 ? (
          <AppText style={styles.muted}>No picks yet. The first ones land here.</AppText>
        ) : (
          recent.map((pk) => (
            <Pressable
              key={pk.pick_no}
              onPress={() => onOpen(pk.player)}
              accessibilityRole="button"
              accessibilityLabel={`Pick ${pk.pick_no}: ${pk.player.name}, ${pk.player.pos}. Open player details`}
              style={[styles.chip, { borderBottomColor: positionColor(pk.player.pos, isDark, colors.borderStrong) }]}
            >
              <AppText style={styles.chipText}>{simDraftPickChip(pk)}</AppText>
            </Pressable>
          ))
        )}
      </ScrollView>
      <CompactModule
        id="draft.board"
        title="Draft board"
        defaultOpen
        parts={[
          { key: 'n', text: `${progress.made}/${progress.total} picks`, strong: true },
          last ? { key: 'last', text: `last ${simDraftPickChip(last)}` } : null,
          { key: 'mine', text: `you ${mine}`, tone: 'accent' },
        ]}
      >
        <View style={styles.mini} testID="mini-board" accessibilityLabel={`Mini draft board, rounds ${win.from} to ${win.to}`}>
          {win.rows.map((row, i) => (
            <View key={win.from + i} style={styles.miniRow}>
              <AppText style={styles.round}>R{win.from + i}</AppText>
              <View style={styles.cells}>
                {row.map((cell) => (
                  <View
                    key={cell.key}
                    style={[
                      styles.cell,
                      cell.pos ? { backgroundColor: positionColor(cell.pos, isDark, colors.borderStrong) } : { borderWidth: 1, borderStyle: 'dashed', borderColor: colors.border },
                      cell.clock && { borderWidth: 2, borderStyle: 'solid', borderColor: colors.accent },
                      cell.you && !cell.clock && { borderWidth: 1.5, borderStyle: 'solid', borderColor: colors.accent },
                    ]}
                  />
                ))}
              </View>
            </View>
          ))}
        </View>
        <Pressable onPress={() => setFull(true)} accessibilityRole="button" style={styles.fullLink}>
          <AppText style={styles.fullText}>Full board</AppText>
        </Pressable>
      </CompactModule>
      <Sheet open={full} onClose={() => setFull(false)} title="Full draft board">
        <SimDraftGrid draft={draft} teams={teams} onOpen={(p) => { setFull(false); onOpen(p); }} />
      </Sheet>
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    wrap: { gap: spacing.sm },
    strip: { gap: 6, alignItems: 'center', minHeight: 32 },
    muted: { fontSize: 12, color: colors.textTertiary },
    chip: { minHeight: 32, paddingHorizontal: spacing.sm, justifyContent: 'center', borderRadius: radii.md, backgroundColor: colors.glass, borderBottomWidth: 3 },
    chipText: { fontSize: 12, fontWeight: '700', color: colors.textPrimary },
    mini: { gap: 3 },
    miniRow: { flexDirection: 'row', alignItems: 'center', gap: 4 },
    round: { width: 24, fontSize: 12, fontWeight: '800', color: colors.textTertiary },
    cells: { flex: 1, flexDirection: 'row', gap: 3 },
    cell: { flex: 1, height: 18, borderRadius: 4 },
    fullLink: { minHeight: 44, justifyContent: 'center', alignSelf: 'flex-start' },
    fullText: { fontSize: 13, fontWeight: '800', color: colors.accent },
  });
}
