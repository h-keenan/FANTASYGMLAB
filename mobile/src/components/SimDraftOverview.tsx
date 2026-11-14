import React, { useMemo, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, View } from 'react-native';

import AppText from './AppText';
import CompactModule from './CompactModule';
import { Sheet } from './Sheet';
import { SimDraftGrid } from './SimDraftGrid';
import { useThemeMode } from '../context/ThemeModeContext';
import { simDraftMiniBoard, simDraftMiniWindow, simDraftPickChip, simDraftProgress, simDraftRecentPicks, simRookieMiniBoard, simRookieRecentChips, type SimMiniCell } from '../lib/simDraft';
import type { SimDraftState, SimGamePlayer } from '../lib/simGame';
import { positionColor, radii, spacing, type ThemeColors } from '../theme';

/**
 * "Who has been drafted", always on the draft page (not behind a tab): a strip of the latest picks and a mini board
 * (rounds x teams of tiny position-coloured cells, your column outlined, the pick on the clock ringed). The mini
 * board shows the rounds around the clock; "Full board" opens the whole grid in a sheet. Web twin: SimDraftOverview.tsx.
 */
export function SimDraftOverview({ draft, teams, onOpen }: { draft: SimDraftState; teams: number; onOpen: (player: SimGamePlayer) => void }) {
  const { colors } = useThemeMode();
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
      <SimRecentStrip
        chips={recent.map((pk) => ({ key: String(pk.pick_no), label: simDraftPickChip(pk), pos: pk.player.pos, aria: `Pick ${pk.pick_no}: ${pk.player.name}, ${pk.player.pos}. Open player details`, onPress: () => onOpen(pk.player) }))}
      />
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
        <SimMiniBoard rows={win.rows} from={win.from} to={win.to} />
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

export interface SimRecentChip {
  key: string;
  label: string;
  pos: string;
  aria?: string;
  onPress?: () => void;
}

/** The latest picks as a horizontally scrolling strip of position-underlined chips (shared by the redraft and rookie drafts). */
export function SimRecentStrip({ chips }: { chips: SimRecentChip[] }) {
  const { colors, isDark } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.strip} accessibilityLabel="Recent picks" testID="recent-picks">
      {chips.length === 0 ? (
        <AppText style={styles.muted}>No picks yet. The first ones land here.</AppText>
      ) : (
        chips.map((chip) => (
          <Pressable
            key={chip.key}
            disabled={!chip.onPress}
            onPress={chip.onPress}
            accessibilityRole={chip.onPress ? 'button' : undefined}
            accessibilityLabel={chip.aria ?? chip.label}
            style={[styles.chip, { borderBottomColor: positionColor(chip.pos, isDark, colors.borderStrong) }]}
          >
            <AppText style={styles.chipText}>{chip.label}</AppText>
          </Pressable>
        ))
      )}
    </ScrollView>
  );
}

/** Rounds x picks of tiny position-coloured cells: yours outlined, the pick on the clock ringed, open slots dashed. */
export function SimMiniBoard({ rows, from, to }: { rows: SimMiniCell[][]; from: number; to: number }) {
  const { colors, isDark } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <View style={styles.mini} testID="mini-board" accessibilityLabel={`Mini draft board, rounds ${from} to ${to}`}>
      {rows.map((row, i) => (
        <View key={from + i} style={styles.miniRow}>
          <AppText style={styles.round}>R{from + i}</AppText>
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
  );
}

/** The rookie draft's always-visible "who has been drafted": recent strip plus the mini board in a CompactModule. */
export function SimRookieOverview({ order, onClockPick, round, made, total }: { order: readonly { n: number; round: number; pick: string; is_yours: boolean; made: { id: string; name: string; pos: string } | null }[]; onClockPick: string | null | undefined; round: number; made: number; total: number }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const win = simDraftMiniWindow(simRookieMiniBoard(order, onClockPick), round);
  const chips = simRookieRecentChips(order);
  return (
    <View style={styles.wrap} testID="rookie-overview">
      <SimRecentStrip chips={chips} />
      <CompactModule id="rookie.board" title="Draft board" defaultOpen parts={[{ key: 'n', text: `${made}/${total} picks`, strong: true }, chips[0] ? { key: 'last', text: `last ${chips[0].label}` } : null]}>
        <SimMiniBoard rows={win.rows} from={win.from} to={win.to} />
      </CompactModule>
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
