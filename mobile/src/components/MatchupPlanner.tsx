import React, { useCallback, useMemo, useRef, useState } from 'react';
import { Linking, Pressable, StyleSheet, TouchableOpacity, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import AppText from './AppText';
import Button from './Button';
import PlayerIdentityRow from './PlayerIdentityRow';
import { SheetModal, SheetScrollView, SwipeDismissCard } from './SwipeDismissSheet';
import ToneBadge from './ToneBadge';
import { useThemeMode } from '../context/ThemeModeContext';
import {
  api,
  type MatchupResponse,
  type MatchupStarter,
  type MatchupWhatIfCandidate,
  type MatchupWhatIfResponse,
  type MatchupWhatIfSlot,
} from '../lib/api';
import {
  applySwap,
  blockedLabel,
  plannerBase,
  sleeperLeagueUrl,
  winPercent,
  type PlannerSource,
} from '../lib/matchupPlanner';
import { slotDisplayLabel } from '../lib/matchupPresentation';
import { trackUse } from '../lib/analytics';
import { radii, scrim, spacing, type ThemeColors } from '../theme';

/**
 * Lineup swap planner for Matchup (same flow as web-next's MatchupPlanner).
 * Planner only: FantasyDesk can't change a Sleeper lineup. Every number comes
 * from POST .../matchup/what-if, which scores the edited lineup with the same
 * win-probability function as the scoreboard.
 */

export interface PlannerState {
  source: PlannerSource;
  slots: MatchupWhatIfSlot[];
  starters: MatchupStarter[] | null;
  result: MatchupWhatIfResponse | null;
  baselinePct: number | null;
  busy: boolean;
  error: string | null;
}

export interface SheetState {
  index: number;
  data: NonNullable<MatchupWhatIfResponse['candidates']> | null;
  error: string | null;
}

export function useLineupPlanner(leagueId: string, matchup: MatchupResponse) {
  const [plan, setPlan] = useState<PlannerState | null>(null);
  const [sheet, setSheet] = useState<SheetState | null>(null);
  const counter = useRef(0);

  const evaluate = useCallback(
    async (slots: MatchupWhatIfSlot[], source: PlannerSource) => {
      const ticket = ++counter.current;
      setPlan((current) => ({
        source,
        slots,
        starters: current?.starters ?? null,
        result: current?.result ?? null,
        baselinePct: current?.baselinePct ?? null,
        busy: true,
        error: null,
      }));
      try {
        const result = await api.postMatchupWhatIf(leagueId, { lineup: slots });
        if (ticket !== counter.current) return;
        setPlan((current) =>
          current
            ? {
                ...current,
                starters: result.lineup ?? current.starters,
                result,
                baselinePct: current.baselinePct ?? winPercent(result.win_probability),
                busy: false,
              }
            : current,
        );
      } catch (err) {
        if (ticket !== counter.current) return;
        setPlan((current) =>
          current
            ? { ...current, busy: false, error: err instanceof Error ? err.message : 'Couldn’t update the lineup.' }
            : current,
        );
      }
    },
    [leagueId],
  );

  const begin = useCallback(
    (source: PlannerSource, keepBaseline: boolean) => {
      const base = plannerBase(matchup, source);
      if (!base) return;
      if (!keepBaseline) trackUse('matchup_swap_planner', 'opened', { leagueId, props: { source_surface: source } });
      setSheet(null);
      setPlan((current) => ({
        source,
        slots: base.slots,
        starters: base.players as MatchupStarter[],
        result: keepBaseline ? (current?.result ?? null) : null,
        baselinePct: keepBaseline ? (current?.baselinePct ?? null) : null,
        busy: true,
        error: null,
      }));
      void evaluate(base.slots, source);
    },
    [matchup, evaluate, leagueId],
  );

  const exit = useCallback(() => {
    counter.current += 1;
    setPlan(null);
    setSheet(null);
  }, []);

  const openSlot = useCallback(
    async (index: number) => {
      if (!plan) return;
      setSheet({ index, data: null, error: null });
      try {
        const result = await api.postMatchupWhatIf(leagueId, { lineup: plan.slots, edit_index: index });
        setSheet((current) =>
          current && current.index === index ? { index, data: result.candidates ?? null, error: null } : current,
        );
      } catch (err) {
        setSheet({ index, data: null, error: err instanceof Error ? err.message : 'Couldn’t load options.' });
      }
    },
    [plan, leagueId],
  );

  const pick = useCallback(
    (candidate: MatchupWhatIfCandidate) => {
      if (!plan || !sheet || !candidate.selectable) return;
      const slots = applySwap(plan.slots, sheet.index, candidate);
      trackUse('matchup_swap_planner', 'swap_applied', { leagueId });
      setSheet(null);
      void evaluate(slots, plan.source);
    },
    [plan, sheet, evaluate, leagueId],
  );

  return {
    plan,
    sheet,
    start: (source: PlannerSource) => begin(source, false),
    resetToSuggested: () => begin('suggested', true),
    exit,
    openSlot,
    pick,
    closeSheet: () => setSheet(null),
  };
}

function toneColor(colors: ThemeColors, tone: 'pro' | 'con' | 'neutral'): string {
  if (tone === 'pro') return colors.successBright;
  if (tone === 'con') return colors.danger;
  return colors.textTertiary;
}

function CandidateRow({ candidate, onPick }: { candidate: MatchupWhatIfCandidate; onPick: () => void }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const { player } = candidate;
  const blocked = blockedLabel(candidate.blocked_reason);
  const delta = candidate.points_delta;
  return (
    <View style={[styles.candidate, !candidate.selectable && styles.candidateDisabled]}>
      <PlayerIdentityRow
        playerId={player.player_id}
        name={player.name}
        position={player.position}
        team={player.team}
        tier={player.tier}
        injuryLabel={player.injury_label}
        trailingValue={
          blocked || delta == null ? null : `${delta > 0 ? '+' : delta < 0 ? '−' : ''}${Math.abs(delta).toFixed(1)}`
        }
        trailingCaption={blocked || delta == null ? null : 'Proj pts'}
        onPress={candidate.selectable ? onPick : undefined}
        showDivider={false}
      />
      {blocked ? (
        <View style={styles.blockedRow}>
          <ToneBadge label={blocked} color={colors.premium} />
        </View>
      ) : null}
      {candidate.bullets.map((bullet) => (
        <View key={bullet.text} style={styles.bulletRow}>
          <View style={[styles.dot, { backgroundColor: toneColor(colors, bullet.tone) }]} />
          <AppText style={styles.bulletText}>{bullet.text}</AppText>
        </View>
      ))}
    </View>
  );
}

/** Eligible players for one slot, pros and cons each. Swipe down, back or the
 * close button dismisses it. */
export function SwapSheet({
  sheet,
  slot,
  onPick,
  onClose,
}: {
  sheet: SheetState;
  slot: string;
  onPick: (candidate: MatchupWhatIfCandidate) => void;
  onClose: () => void;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const candidates = sheet.data?.candidates ?? [];
  return (
    <SheetModal visible transparent animationType="fade" onRequestClose={onClose}>
      <Pressable style={styles.backdrop} onPress={onClose}>
        <SwipeDismissCard style={styles.sheet} onDismiss={onClose}>
          <View style={styles.sheetHeader}>
            <AppText style={styles.sheetTitle}>{slotDisplayLabel(slot)} options</AppText>
            <TouchableOpacity onPress={onClose} hitSlop={8} accessibilityLabel="Close">
              <Ionicons name="close" size={20} color={colors.textSecondary} />
            </TouchableOpacity>
          </View>
          <SheetScrollView style={styles.sheetBody}>
            {sheet.error ? (
              <AppText style={[styles.muted, { color: colors.danger }]}>{sheet.error}</AppText>
            ) : !sheet.data ? (
              <AppText style={styles.muted}>Loading…</AppText>
            ) : sheet.data.slot_locked ? (
              <AppText style={styles.muted}>This player’s game has started, so the slot is locked.</AppText>
            ) : candidates.length === 0 ? (
              <AppText style={styles.muted}>No one else on your roster can fill this slot.</AppText>
            ) : (
              candidates.map((candidate, index) => {
                const previous = candidates[index - 1];
                const startsGroup = candidate.selectable && !!candidate.currently_starting
                  && (!previous || !previous.currently_starting || !previous.selectable);
                return (
                  <View key={candidate.player.player_id}>
                    {startsGroup && index > 0 ? (
                      <AppText style={[styles.muted, { marginTop: 12, textTransform: 'uppercase', fontWeight: '700' }]}>
                        Swap with another starter
                      </AppText>
                    ) : null}
                    <CandidateRow candidate={candidate} onPick={() => onPick(candidate)} />
                  </View>
                );
              })
            )}
          </SheetScrollView>
        </SwipeDismissCard>
      </Pressable>
    </SheetModal>
  );
}

/** Edit lineup, or while editing: the win change, Reset to suggested,
 * Open in Sleeper and Done. */
export function PlannerBar({
  editing,
  busy,
  error,
  baselinePct,
  currentPct,
  leagueId,
  onEdit,
  onReset,
  onDone,
}: {
  editing: boolean;
  busy: boolean;
  error: string | null;
  baselinePct: number | null;
  currentPct: number | null;
  leagueId: string;
  onEdit: () => void;
  onReset: () => void;
  onDone: () => void;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  if (!editing) {
    return <Button label="Edit lineup" variant="secondary" onPress={onEdit} />;
  }
  const changed = baselinePct != null && currentPct != null && baselinePct !== currentPct;
  return (
    <View style={styles.bar}>
      <View style={styles.barRow}>
        <Button label="Reset to suggested" variant="secondary" onPress={onReset} disabled={busy} style={styles.barButton} />
        <Button label="Done" variant="ghost" onPress={onDone} />
      </View>
      <TouchableOpacity
        onPress={() => void Linking.openURL(sleeperLeagueUrl(leagueId))}
        accessibilityRole="link"
        accessibilityLabel="Open in Sleeper"
      >
        <AppText style={styles.link}>Open in Sleeper</AppText>
      </TouchableOpacity>
      {error ? (
        <AppText style={[styles.barNote, { color: colors.danger }]}>{error}</AppText>
      ) : changed ? (
        <AppText style={styles.barNote}>
          Win probability {baselinePct}% to {currentPct}% with your edits.
        </AppText>
      ) : null}
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    backdrop: { flex: 1, backgroundColor: scrim, alignItems: 'center', justifyContent: 'center', padding: spacing.lg },
    sheet: {
      backgroundColor: colors.backgroundElevated,
      borderRadius: radii.lg,
      borderWidth: 1,
      borderColor: colors.cardBorder,
      padding: spacing.lg,
      width: '100%',
      maxWidth: 420,
      maxHeight: '80%',
    },
    sheetHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: spacing.sm },
    sheetTitle: { fontSize: 18, fontWeight: '800', color: colors.textPrimary },
    sheetBody: { flexGrow: 0 },
    muted: { fontSize: 13, color: colors.textTertiary, paddingVertical: spacing.md },
    candidate: {
      paddingVertical: spacing.sm,
      gap: 4,
      borderBottomWidth: StyleSheet.hairlineWidth,
      borderBottomColor: colors.border,
    },
    candidateDisabled: { opacity: 0.6 },
    blockedRow: { flexDirection: 'row', paddingLeft: spacing.xs },
    bulletRow: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingLeft: spacing.xs },
    dot: { width: 6, height: 6, borderRadius: 3 },
    bulletText: { fontSize: 12, color: colors.textSecondary },
    bar: { gap: spacing.sm },
    barRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
    barButton: { flex: 1 },
    link: { fontSize: 13, fontWeight: '700', color: colors.accent },
    barNote: { fontSize: 12, color: colors.textSecondary },
  });
}
