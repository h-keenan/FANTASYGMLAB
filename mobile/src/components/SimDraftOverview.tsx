import React, { useMemo, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, View } from 'react-native';

import AppText from './AppText';
import CompactModule from './CompactModule';
import CompactPlayerCard from './CompactPlayerCard';
import { LetterGrade } from './LetterGrade';
import { MotionIn } from './Motion';
import { SimTeamIdentity } from './SimTeamIdentity';
import { Sheet } from './Sheet';
import { SimDraftGrid } from './SimDraftGrid';
import { useThemeMode } from '../context/ThemeModeContext';
import { simDraftMiniBoard, simDraftMiniWindow, simDraftPickChip, simDraftProgress, simDraftRecentPicks, simRookieMiniBoard, simRookieRecentCards, simRookieRecentChips, type SimMiniCell, type SimRecentPickCard, type SimSurvival } from '../lib/simDraft';
import type { SimDraftState, SimGamePlayer } from '../lib/simGame';
import { positionColor, radii, spacing, type ThemeColors } from '../theme';

/**
 * "Who has been drafted", always on the draft page (not behind a tab). The recent picks live in the pinned clock area
 * (`SimRecentStrip`); this is the mini board module under it: rounds x teams of tiny position-coloured cells, your column
 * outlined, the pick on the clock ringed; "Full board" opens the whole grid (`onFullBoard`, the page owns the sheet).
 * Web twin: SimDraftOverview.tsx.
 */
export function SimDraftOverview({ draft, teams, onFullBoard }: { draft: SimDraftState; teams: number; onFullBoard: () => void }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const recent = simDraftRecentPicks(draft.picks, 1);
  const progress = simDraftProgress(draft, teams);
  const mini = useMemo(() => simDraftMiniBoard(draft, teams), [draft, teams]);
  const win = simDraftMiniWindow(mini.rows, progress.round);
  const mine = (draft.picks ?? []).filter((p) => draft.teams?.find((t) => t.team_id === p.team_id)?.is_you).length;
  const last = recent[0];
  return (
    <View style={styles.wrap} testID="draft-overview">
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
        <Pressable onPress={onFullBoard} accessibilityRole="button" style={styles.fullLink}>
          <AppText style={styles.fullText}>Full board</AppText>
        </Pressable>
      </CompactModule>
    </View>
  );
}

/** The full draft grid in a sheet (the strip's "Full board" and the board module's link both open it). */
export function SimFullBoardSheet({ open, onClose, draft, teams, onOpen }: { open: boolean; onClose: () => void; draft: SimDraftState; teams: number; onOpen: (player: SimGamePlayer) => void }) {
  return (
    <Sheet open={open} onClose={onClose} title="Full draft board">
      <SimDraftGrid draft={draft} teams={teams} onOpen={(p) => { onClose(); onOpen(p); }} />
    </Sheet>
  );
}

/**
 * The latest picks as a horizontally scrolling strip of compact player cards: pick number, the picking team's logo
 * (SimTeamIdentity), avatar, name, position and letter grade. A card opens the player; "Full board" opens the whole board.
 * Lives in the pinned clock area (redraft and rookie drafts). Web twin: SimDraftOverview.tsx.
 */
export function SimRecentStrip({ cards, onOpenPlayer, onFullBoard }: { cards: SimRecentPickCard[]; onOpenPlayer?: (card: SimRecentPickCard) => void; onFullBoard?: () => void }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <View style={styles.stripWrap} testID="recent-picks-wrap">
      <View style={styles.stripHead}>
        <AppText style={styles.kicker}>Just drafted</AppText>
        {onFullBoard ? (
          <Pressable onPress={onFullBoard} accessibilityRole="button" style={styles.boardLink} testID="recent-full-board">
            <AppText style={styles.fullText}>Full board</AppText>
          </Pressable>
        ) : null}
      </View>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.strip} accessibilityLabel="Recent picks" testID="recent-picks">
        {cards.length === 0 ? (
          <AppText style={styles.muted}>No picks yet. The first ones land here.</AppText>
        ) : (
          cards.map((card, i) => (
            <MotionIn key={card.key} index={i} count={cards.length}>
              <Pressable
                disabled={!onOpenPlayer}
                onPress={onOpenPlayer ? () => onOpenPlayer(card) : undefined}
                accessibilityRole={onOpenPlayer ? 'button' : undefined}
                accessibilityLabel={card.aria}
                style={[styles.card, card.isYou && { borderColor: colors.accent }]}
                testID="recent-pick-card"
              >
                <View style={styles.cardTop}>
                  <AppText style={styles.pickNo}>{card.pickLabel}</AppText>
                  {card.teamName ? <SimTeamIdentity name={card.teamName} size="chip" hideName /> : null}
                </View>
                <CompactPlayerCard player={card.player} testID="recent-pick-player" trailing={card.grade ? <LetterGrade grade={card.grade} size="xs" /> : undefined} />
              </Pressable>
            </MotionIn>
          ))
        )}
      </ScrollView>
    </View>
  );
}

/** "Who survives to my pick": one calm line from public ADP, a running position and your needs (`simDraftSurvival`). */
export function SimSurvivalLine({ survival }: { survival: SimSurvival | null }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  if (!survival) return null;
  return (
    <AppText style={styles.survival} testID="draft-survival">
      <AppText style={[styles.survival, { color: colors.accent, fontWeight: '800' }]}>Before your pick </AppText>
      {survival.text}
    </AppText>
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

/** The rookie draft's always-visible "who has been drafted": the recent strip plus the mini board in a CompactModule. */
export function SimRookieOverview({ order, onClockPick, round, made, total }: { order: readonly { n: number; round: number; pick: string; is_yours: boolean; made: { id: string; name: string; pos: string } | null }[]; onClockPick: string | null | undefined; round: number; made: number; total: number }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const win = simDraftMiniWindow(simRookieMiniBoard(order, onClockPick), round);
  const cards = simRookieRecentCards(order);
  const last = simRookieRecentChips(order, 1)[0];
  return (
    <View style={styles.wrap} testID="rookie-overview">
      <SimRecentStrip cards={cards} />
      <CompactModule id="rookie.board" title="Draft board" defaultOpen parts={[{ key: 'n', text: `${made}/${total} picks`, strong: true }, last ? { key: 'last', text: `last ${last.label}` } : null]}>
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
    stripWrap: { gap: 4 },
    stripHead: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
    kicker: { fontSize: 12, fontWeight: '800', letterSpacing: 0.6, textTransform: 'uppercase', color: colors.textTertiary },
    boardLink: { minHeight: 32, justifyContent: 'center' },
    card: { width: 168, gap: 4, padding: spacing.sm, borderRadius: radii.md, backgroundColor: colors.glass, borderWidth: 1, borderColor: 'transparent' },
    cardTop: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
    pickNo: { fontSize: 12, fontWeight: '800', color: colors.textTertiary },
    survival: { fontSize: 12.5, color: colors.textSecondary },
    fullLink: { minHeight: 44, justifyContent: 'center', alignSelf: 'flex-start' },
    fullText: { fontSize: 13, fontWeight: '800', color: colors.accent },
  });
}
