import React, { useEffect, useMemo, useState, type ReactNode } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import AppText from './AppText';
import Button from './Button';
import Collapsible from './Collapsible';
import { SimPlayerLine, SimSheet, SimToneBadge, createSimStyles, simToneColor, type SimCtx } from './SimGameParts';
import ToneBadge from './ToneBadge';
import { useThemeMode } from '../context/ThemeModeContext';
import { api } from '../lib/api';
import { isSimRookieNoticeSeen, setSimRookieNoticeSeen } from '../lib/simRookieNotice';
import {
  SIM_GENERATED_CLASS_LABEL,
  SIM_GENERATED_CLASS_NOTICE,
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
 * A collapsible block for the dynasty screens: a thin adapter over the shared
 * Collapsible (mirrors web-next), so the Team tab, the offseason screens and
 * the dynasty result open, close and remember their state like every other
 * fold. Collapsed by default so a phone screen shows the summary first.
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
  return (
    <Collapsible
      id={`dyn.${testID ?? title}`}
      testID={testID}
      accent={simToneColor(tone === 'muted' ? 'accent' : tone, colors)}
      defaultOpen={defaultOpen}
      title={
        <View style={styles.collapseTitleRow}>
          <AppText style={styles.collapseTitle}>{title}</AppText>
          {badge}
        </View>
      }
      summary={summary ? <AppText style={styles.collapseSummary}>{summary}</AppText> : undefined}
    >
      {children}
    </Collapsible>
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
        {trailing}
      </View>
    </View>
  );
}

/** A player or a pick, whichever the asset is (counter chips, inbox offers, verdicts). */
export function SimAssetLine({ asset, trailing, onOpen }: { asset: SimTradeAsset; trailing?: ReactNode; onOpen?: (player: SimGamePlayer) => void }) {
  if (simIsPick(asset)) return <SimPickLine pick={asset} trailing={trailing} />;
  return <SimPlayerLine player={asset} onOpen={onOpen} trailing={trailing} />;
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
          <AppText style={styles.yearLabel}>{group.label}</AppText>
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

/**
 * The small "Generated class - strong" chip with an info affordance. Tapping it
 * opens the notice (the parent owns the sheet). hitSlop keeps a 44pt target.
 */
export function SimGeneratedChip({ label = SIM_GENERATED_CLASS_LABEL, onInfo, compact = false }: { label?: string; onInfo: () => void; compact?: boolean }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <Pressable
      onPress={onInfo}
      hitSlop={compact ? { top: 14, bottom: 14, left: 8, right: 8 } : { top: 8, bottom: 8, left: 8, right: 8 }}
      accessibilityRole="button"
      accessibilityLabel={`${label}. ${SIM_GENERATED_CLASS_NOTICE}`}
      testID="generated-chip"
      style={styles.generatedChip}
    >
      <AppText style={styles.generatedChipText} numberOfLines={1}>{label}</AppText>
      <Ionicons name="information-circle-outline" size={13} color={colors.accent} />
    </Pressable>
  );
}

/** The notice sheet behind every Generated class chip and the first-time popup. */
export function SimGeneratedNoticeSheet({ onClose }: { onClose: () => void }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <SimSheet title="Simulated rookie class" onClose={onClose}>
      <View style={styles.noticeBody} testID="generated-notice">
        <AppText style={styles.noticeText}>{SIM_GENERATED_CLASS_NOTICE}</AppText>
        <Button label="Got it" onPress={onClose} />
      </View>
    </SimSheet>
  );
}

/** Shows the notice once per game, the first time a rookie draft screen opens. */
export function SimRookieNoticeGate({ gameId }: { gameId: string }) {
  const [open, setOpen] = useState(false);
  useEffect(() => {
    let cancelled = false;
    void isSimRookieNoticeSeen(gameId).then((seen) => {
      if (!cancelled) setOpen(!seen);
    });
    return () => {
      cancelled = true;
    };
  }, [gameId]);
  if (!open) return null;
  return (
    <SimGeneratedNoticeSheet
      onClose={() => {
        void setSimRookieNoticeSeen(gameId);
        setOpen(false);
      }}
    />
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
    generatedChip: {
      flexDirection: 'row',
      alignItems: 'center',
      alignSelf: 'flex-start',
      gap: 4,
      paddingHorizontal: 8,
      paddingVertical: 3,
      borderRadius: 999,
      borderWidth: 1,
      borderColor: colors.accent,
      backgroundColor: colors.accentMuted,
    },
    generatedChipText: { fontSize: 12, fontWeight: '800', letterSpacing: 0.6, textTransform: 'uppercase', color: colors.accent },
    noticeBody: { gap: spacing.md, paddingBottom: spacing.sm },
    noticeText: { fontSize: 15, lineHeight: 22, color: colors.textSecondary },
    yearLabel: { paddingTop: spacing.xs, fontSize: 13, fontWeight: '700', color: colors.textSecondary },
  });
}
