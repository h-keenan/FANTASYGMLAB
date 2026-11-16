import React, { useMemo, useState } from 'react';
import { StyleSheet, View } from 'react-native';

import AccentCard from './AccentCard';
import AppText from './AppText';
import Button from './Button';
import CompactModule from './CompactModule';
import ConfirmInPlace from './ConfirmInPlace';
import EmptyState from './EmptyState';
import { LetterGrade } from './LetterGrade';
import { Sheet } from './Sheet';
import SegmentedTabBar from './SegmentedTabBar';
import { SimTeamLogo } from './SimTeamIdentity';
import { SimProgressBar, simToneColor } from './SimGameParts';
import ToneBadge from './ToneBadge';
import { useThemeMode } from '../context/ThemeModeContext';
import { simGameLiteLine, simSetupBody, type SimGameCreateBody, type SimGameLite, type SimGameOptionsResponse, type SimSetupState } from '../lib/simGame';
import { simHubRow } from '../lib/simHub';
import { simHubEmptyHint, simHubGameName, simHubMode, simHubPresetChips, simHubPresets, type SimPresetId } from '../lib/simHubPresets';
import type { SimGradeInput } from '../lib/simGrade';
import { spacing, type ThemeColors } from '../theme';

/**
 * The Fantasy Sim hub (docs/audits/ui-pass-3/sim-hub-options.html, V1), native twin of web-next/src/components/SimHub.tsx.
 * A "New game" button in the header opens a presets sheet (Quick preselected; Customize everything opens the full setup
 * seeded with the preset). Saved games are the page: one tappable row each (crest, name, shape, letter grade once
 * finished, progress, phase), no chevrons. First-timers get the explainer open and a nudge; returning players get it
 * collapsed to one line. Presets and copy: lib/simHubPresets.ts (byte-identical twin).
 */
export default function SimHub({
  games,
  options,
  block,
  isPremium,
  managing,
  deletingId,
  creating,
  onManage,
  onGoPro,
  onOpen,
  onDelete,
  onStart,
  onCustomize,
}: {
  games: SimGameLite[];
  options: SimGameOptionsResponse | null;
  /** Why New game is unavailable (the save limit), or null. */
  block: string | null;
  isPremium: boolean | undefined;
  managing: boolean;
  deletingId: string | null;
  creating: boolean;
  onManage: () => void;
  onGoPro: () => void;
  onOpen: (id: string) => void;
  onDelete: (id: string) => Promise<boolean>;
  onStart: (body: SimGameCreateBody) => void;
  onCustomize: (seed: SimSetupState) => void;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [sheetOpen, setSheetOpen] = useState(false);
  const first = simHubMode(games.length) === 'first';
  return (
    <>
      <View style={styles.header}>
        <AppText style={styles.pageTitle} accessibilityRole="header">Fantasy Sim</AppText>
        <Button label="New game" disabled={Boolean(block)} onPress={() => setSheetOpen(true)} />
      </View>
      {block ? (
        <View style={styles.tight}>
          <AppText style={styles.body} testID="new-game-block">{block}</AppText>
          <View style={styles.wrapRow}>
            {isPremium === false ? <Button label="Go Pro" variant="premium" size="sm" onPress={onGoPro} /> : null}
            <Button label="Manage games / delete one" variant="secondary" size="sm" onPress={onManage} />
          </View>
        </View>
      ) : null}
      <CompactModule
        id="sim.hub.about"
        title="What is this"
        label="What is Fantasy Sim"
        parts={[{ key: 'line', text: 'Be the GM. Win the season.', strong: true }, { key: 'tags', text: 'Draft, trade, recaps', tone: 'muted' }]}
        defaultOpen={first}
        testID="sim-hub-about"
      >
        <AppText style={styles.body}>
          Draft a 12-team league against AI managers, set your lineup, work waivers and trades week by week, and take on the playoffs. At the end you get a grade. Nothing here touches your real leagues.
        </AppText>
      </CompactModule>
      <View style={styles.stack}>
        <AppText style={styles.kicker}>{`Your games${games.length ? ` · ${games.length}` : ''}`}</AppText>
        {games.length === 0 ? (
          <EmptyState icon="american-football-outline" title="No games yet" subtitle={simHubEmptyHint(simHubPresets(options))} />
        ) : (
          <>
            {managing ? <AppText style={styles.muted}>Tap the trash can on a game to delete it.</AppText> : null}
            {games.map((g) => (
              <ConfirmInPlace
                key={g.id}
                variant="icon"
                label={`Delete game: ${simGameLiteLine(g)}`}
                prompt="Delete this game? It can't be undone."
                confirmLabel="Delete"
                keepLabel="Keep"
                errorText="Could not delete it. Try again."
                disabled={deletingId !== null}
                onConfirm={() => onDelete(g.id)}
                rowContent={<SavedGameRow game={g} onPress={() => onOpen(g.id)} />}
              />
            ))}
            <AppText style={[styles.muted, styles.center]}>Tap a game to continue</AppText>
          </>
        )}
      </View>
      <NewGameSheet
        open={sheetOpen}
        options={options}
        creating={creating}
        onClose={() => setSheetOpen(false)}
        onStart={(body) => {
          setSheetOpen(false);
          onStart(body);
        }}
        onCustomize={(seed) => {
          setSheetOpen(false);
          onCustomize(seed);
        }}
      />
    </>
  );
}

function SavedGameRow({ game, onPress }: { game: SimGameLite; onPress: () => void }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const row = simHubRow(game);
  const tone = row.chip.tone;
  const done = game.status === 'complete';
  const grade: SimGradeInput | null = done && game.grade_letter ? { grade: game.grade_letter as SimGradeInput['grade'] } : null;
  const name = simHubGameName(game);
  return (
    <AccentCard accent={done ? simToneColor(tone, colors) : colors.accent} compact onPress={onPress}>
      <View style={styles.rowHead}>
        <SimTeamLogo name={`${name} ${game.seed}`} size="card" />
        <View style={styles.grow}>
          <AppText style={styles.rowName}>{name}</AppText>
          <AppText style={styles.muted}>{row.meta.split(' · ').slice(1).join(' · ')}</AppText>
        </View>
        {grade ? <LetterGrade grade={grade} size="md" /> : null}
      </View>
      {row.progress ? <SimProgressBar done={row.progress.done} total={row.progress.total} tone={tone} label={`${row.progress.done} of ${row.progress.total} weeks played`} /> : null}
      <View style={styles.rowBetween}>
        <ToneBadge label={done ? 'Finished' : row.title} color={simToneColor(done ? 'muted' : 'accent', colors)} size="xs" />
        <AppText style={styles.muted}>
          {row.played}
          {row.open ? <AppText style={[styles.muted, { color: colors.accent, fontWeight: '700' }]}>{row.played ? ' · ' : ''}Continue</AppText> : null}
        </AppText>
      </View>
    </AccentCard>
  );
}

function NewGameSheet({
  open,
  options,
  creating,
  onClose,
  onStart,
  onCustomize,
}: {
  open: boolean;
  options: SimGameOptionsResponse | null;
  creating: boolean;
  onClose: () => void;
  onStart: (body: SimGameCreateBody) => void;
  onCustomize: (seed: SimSetupState) => void;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const presets = useMemo(() => simHubPresets(options), [options]);
  const [picked, setPicked] = useState<SimPresetId>('quick');
  const preset = presets.find((p) => p.id === picked) ?? presets[0];
  const chips = simHubPresetChips(preset);
  return (
    <Sheet open={open} onClose={onClose} title="New game" size="sm" testID="sim-new-game-sheet">
      <View style={styles.stack}>
        {presets.length > 1 ? (
          <SegmentedTabBar<SimPresetId> options={presets.map((p) => ({ key: p.id, label: p.label }))} active={preset.id} onChange={setPicked} />
        ) : null}
        <AppText style={styles.body}>{preset.blurb}</AppText>
        <View style={styles.wrapRow} testID="sim-preset-chips">
          {chips.map((chip) => (
            <ToneBadge key={chip} label={chip} color={colors.accent} size="xs" />
          ))}
        </View>
        <Button label={creating ? 'Starting...' : preset.action} disabled={creating} onPress={() => onStart(simSetupBody(preset.state))} />
        <Button label="Customize everything" variant="ghost" onPress={() => onCustomize(preset.state)} />
      </View>
    </Sheet>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: spacing.md },
    pageTitle: { fontSize: 22, fontWeight: '800', color: colors.textPrimary },
    stack: { gap: spacing.md },
    tight: { gap: spacing.xs },
    wrapRow: { flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', gap: spacing.sm },
    kicker: { fontSize: 12, fontWeight: '800', letterSpacing: 0.6, textTransform: 'uppercase', color: colors.textTertiary },
    body: { fontSize: 15, lineHeight: 21, color: colors.textSecondary },
    muted: { fontSize: 13, lineHeight: 18, color: colors.textTertiary },
    center: { textAlign: 'center' },
    grow: { flex: 1, minWidth: 0 },
    rowHead: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
    rowName: { fontSize: 15, fontWeight: '700', color: colors.textPrimary },
    rowBetween: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: spacing.sm },
  });
}
