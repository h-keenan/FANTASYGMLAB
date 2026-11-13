import React, { useEffect, useMemo, useState, type ReactNode } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import AccentCard from './AccentCard';
import AppText from './AppText';
import Button from './Button';
import { SimPlayerLine, SimStat, SimToneBadge, createSimStyles, simToneColor, type SimCtx } from './SimGameParts';
import ToneBadge from './ToneBadge';
import { useThemeMode } from '../context/ThemeModeContext';
import { api } from '../lib/api';
import {
  simIsPick,
  simPickGroups,
  simPickLabelText,
  simPickSlotHint,
  simPickViaLine,
  simPlayerChips,
  type SimGamePlayer,
  type SimGameTone,
  type SimPickAsset,
  type SimPicksResponse,
  type SimTradeAsset,
} from '../lib/simGame';
import { spacing, type ThemeColors } from '../theme';

/**
 * A collapsible block: a full-width header (title, one summary line, chevron)
 * over a body. Collapsed by default so a phone screen shows the summary first.
 * Used by the Team tab, the offseason screens and the dynasty result.
 */
export function SimCollapse({
  title,
  summary,
  defaultOpen = false,
  tone = 'muted',
  badge,
  children,
  testID,
}: {
  title: string;
  summary?: string;
  defaultOpen?: boolean;
  tone?: SimGameTone;
  badge?: ReactNode;
  children: ReactNode;
  testID?: string;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [open, setOpen] = useState(defaultOpen);
  return (
    <AccentCard accent={simToneColor(tone === 'muted' ? 'accent' : tone, colors)} compact>
      <Pressable
        style={styles.collapseHead}
        onPress={() => setOpen((v) => !v)}
        accessibilityRole="button"
        accessibilityState={{ expanded: open }}
        accessibilityLabel={`${title}${summary ? `. ${summary}` : ''}`}
        testID={testID}
      >
        <View style={styles.collapseText}>
          <View style={styles.collapseTitleRow}>
            <AppText style={styles.collapseTitle}>{title}</AppText>
            {badge}
          </View>
          {summary ? <AppText style={styles.collapseSummary}>{summary}</AppText> : null}
        </View>
        <Ionicons name={open ? 'chevron-up' : 'chevron-down'} size={18} color={colors.textTertiary} />
      </Pressable>
      {open ? <View style={styles.collapseBody}>{children}</View> : null}
    </AccentCard>
  );
}

/** IR / TAXI / ROOKIE / OUT n wks chips for one roster row. */
export function SimPlayerChips({ player }: { player: Pick<SimGamePlayer, 'squad' | 'rookie' | 'status' | 'out_weeks'> }) {
  const chips = simPlayerChips(player);
  if (chips.length === 0) return null;
  return (
    <>
      {chips.map((chip) => (
        <SimToneBadge key={chip.key} label={chip.label} tone={chip.tone} />
      ))}
    </>
  );
}

/** One draft pick as a list row: "2027 Round 1 (early)", where it came from, and its value. */
export function SimPickLine({ pick, trailing, selected = false, draftYear }: { pick: SimPickAsset; trailing?: ReactNode; selected?: boolean; draftYear?: number | null }) {
  const { colors } = useThemeMode();
  const common = useMemo(() => createSimStyles(colors), [colors]);
  const styles = useMemo(() => createStyles(colors), [colors]);
  const via = simPickViaLine(pick);
  const sub = [via, simPickSlotHint(pick, draftYear)].filter(Boolean).join(' · ');
  return (
    <View style={[styles.pickLine, selected && styles.pickSelected]} testID="pick-row">
      <View style={[common.row, styles.pickMain]}>
        <ToneBadge label={`R${pick.round}`} color={colors.accent} size="xs" />
        <View style={common.grow}>
          <AppText style={common.bodyStrong}>{simPickLabelText(pick)}</AppText>
          {sub ? <AppText style={common.muted}>{sub}</AppText> : null}
        </View>
      </View>
      <View style={styles.pickTrailing}>
        <SimStat label="Value" value={Math.round(pick.value)} />
        {trailing}
      </View>
    </View>
  );
}

/** A player or a pick, whichever the asset is (counter chips, inbox offers, verdicts). */
export function SimAssetLine({ asset, trailing, onOpen }: { asset: SimTradeAsset; trailing?: ReactNode; onOpen?: (player: SimGamePlayer) => void }) {
  if (simIsPick(asset)) return <SimPickLine pick={asset} trailing={trailing} />;
  return <SimPlayerLine player={asset} onOpen={onOpen} trailing={trailing ?? <SimStat label="Value" value={Math.round(asset.value)} />} />;
}

/** The picks of the game (every team's), or null until loaded; null for a redraft game. */
export function useSimPicks(ctx: Pick<SimCtx, 'gameId' | 'game' | 'tick'>): SimPicksResponse | null {
  const dynasty = ctx.game.settings.mode === 'dynasty';
  const [picks, setPicks] = useState<SimPicksResponse | null>(null);
  useEffect(() => {
    if (!dynasty) return;
    let cancelled = false;
    api
      .getSimPicks(ctx.gameId)
      .then((body) => {
        if (!cancelled && !body.reason) setPicks(body);
      })
      .catch(() => {
        /* the picks group just stays empty */
      });
    return () => {
      cancelled = true;
    };
  }, [dynasty, ctx.gameId, ctx.tick]);
  return dynasty ? picks : null;
}

/**
 * The Picks group inside a trade asset picker: one team's picks grouped by
 * year then round. `selected` / `onToggle` are the same id-based state as the
 * players beside it (pick ids are plain strings).
 */
export function SimPickGroup({
  picks,
  selected,
  onToggle,
  side,
  draftYear,
  full = false,
}: {
  picks: SimPickAsset[];
  selected: string[];
  onToggle: (id: string) => void;
  side: 'give' | 'get';
  draftYear?: number | null;
  /** The side already holds its maximum; unselected picks are disabled. */
  full?: boolean;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const groups = simPickGroups(picks);
  if (groups.length === 0) return null;
  return (
    <View testID={`pick-group-${side}`}>
      <AppText style={styles.groupKicker}>{side === 'give' ? 'Your picks' : 'Their picks'}</AppText>
      {groups.map((group) => (
        <View key={group.season}>
          <AppText style={styles.yearLabel}>{group.season}</AppText>
          {group.rounds
            .flatMap((r) => r.picks)
            .map((pick) => {
              const on = selected.includes(pick.id);
              return (
                <SimPickLine
                  key={pick.id}
                  pick={pick}
                  selected={on}
                  draftYear={draftYear}
                  trailing={
                    <Button
                      size="sm"
                      variant={on ? 'primary' : 'secondary'}
                      disabled={!on && full}
                      label={on ? (side === 'give' ? 'Giving' : 'Getting') : side === 'give' ? 'Give' : 'Get'}
                      onPress={() => onToggle(pick.id)}
                    />
                  }
                />
              );
            })}
        </View>
      ))}
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    collapseHead: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: spacing.sm, minHeight: 44 },
    collapseText: { flex: 1, minWidth: 0 },
    collapseTitleRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
    collapseTitle: { fontSize: 15, fontWeight: '800', color: colors.textPrimary },
    collapseSummary: { fontSize: 13, color: colors.textTertiary },
    collapseBody: { gap: spacing.xs, paddingTop: spacing.xs },
    pickLine: {
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent: 'space-between',
      flexWrap: 'wrap',
      gap: spacing.sm,
      paddingVertical: spacing.sm,
      minHeight: 44,
      borderBottomWidth: StyleSheet.hairlineWidth,
      borderBottomColor: colors.border,
    },
    pickSelected: { backgroundColor: colors.accentMuted },
    pickMain: { flex: 1, minWidth: 180 },
    pickTrailing: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, marginLeft: 'auto' },
    groupKicker: { paddingTop: spacing.sm, fontSize: 12.5, fontWeight: '800', letterSpacing: 0.8, textTransform: 'uppercase', color: colors.textTertiary },
    yearLabel: { paddingTop: spacing.xs, fontSize: 13, fontWeight: '700', color: colors.textSecondary },
  });
}
