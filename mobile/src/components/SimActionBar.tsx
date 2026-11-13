import React, { useEffect, useMemo, useState } from 'react';
import { ActivityIndicator, Alert, Pressable, StyleSheet, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import AppText from './AppText';
import Button from './Button';
import SimGlyph from './SimGlyph';
import type { SimCtx } from './SimGameParts';
import { useSimAutoSet } from './useSimAutoSet';
import { useThemeMode } from '../context/ThemeModeContext';
import { api } from '../lib/api';
import { simAdvanceLabel } from '../lib/simGame';
import { simAdvanceState, simEmptySlotLabels } from '../lib/simLayout';
import { ORB_SIZE } from '../lib/orbLayout';
import { radii, spacing, type ThemeColors } from '../theme';

/** Height of the bar's controls row (the reason line, when shown, adds ~20). */
export const SIM_ACTION_BAR_HEIGHT = 60;

/**
 * Bottom of the stack: where the bar sits, just above the floating GM orb
 * (which is anchored bottom-center at the safe-area bottom).
 */
export function useSimActionBarBottom(): number {
  const insets = useSafeAreaInsets();
  return Math.max(insets.bottom, 0) + ORB_SIZE + spacing.sm;
}

/**
 * The persistent bottom action bar for the in-season tabs (mirrors web-next's
 * SimActionBar): Advance week ("Week 4 -> 5", disabled only when a cut is owed;
 * an empty slot warns and asks to confirm) and a secondary Auto-set pill. It floats
 * above the GM orb; the screen adds matching bottom padding.
 */
export default function SimActionBar({ ctx, paywalled, advancing, onAdvance, onGoPro, onTab }: { ctx: SimCtx; paywalled: boolean; advancing: boolean; onAdvance: () => void; onGoPro: () => void; onTab?: (tab: 'team' | 'players') => void }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const bottom = useSimActionBarBottom();
  const { gameId, game } = ctx;
  const [emptySlots, setEmptySlots] = useState<string[]>([]);
  const auto = useSimAutoSet(ctx);

  useEffect(() => {
    let cancelled = false;
    api
      .getSimLineup(gameId)
      .then((body) => {
        if (!cancelled) setEmptySlots(simEmptySlotLabels(body.slots ?? []));
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [gameId, ctx.tick, game.week]);

  const state = simAdvanceState(game, emptySlots);
  // An empty slot is a warning, not a block: confirm, with shortcuts to fix it first.
  const tapAdvance = () => {
    if (!state.confirm) {
      onAdvance();
      return;
    }
    Alert.alert('Empty starting slot', state.confirm, [
      { text: 'Cancel', style: 'cancel' },
      ...(onTab ? [{ text: 'Fill from bench', onPress: () => onTab('team') }, { text: 'Free agents', onPress: () => onTab('players') }] : []),
      { text: 'Advance anyway', style: 'destructive' as const, onPress: onAdvance },
    ]);
  };
  return (
    <View style={[styles.bar, { bottom }]} testID="sim-action-bar">
      {state.warning && !state.reason && !paywalled ? <AppText style={styles.reason}>{state.warning}</AppText> : null}
      {state.reason && !paywalled ? (
        <AppText style={styles.reason} accessibilityRole="alert">
          {state.reason}
        </AppText>
      ) : null}
      <View style={styles.row}>
        <Pressable
          onPress={auto.run}
          disabled={auto.busy || auto.optimal || paywalled}
          accessibilityRole="button"
          accessibilityLabel={auto.optimal ? 'Lineup is optimal' : 'Auto-set best lineup'}
          accessibilityState={{ disabled: auto.busy || auto.optimal || paywalled, busy: auto.busy }}
          style={[styles.pill, (auto.optimal || paywalled) && styles.pillOff]}
        >
          {auto.busy ? <ActivityIndicator size="small" color={colors.textSecondary} /> : <SimGlyph name={auto.optimal ? 'check' : 'spark'} color={colors.textPrimary} size={16} />}
          <AppText style={styles.pillLabel}>{auto.optimal ? 'Optimal' : 'Auto-set'}</AppText>
        </Pressable>
        <View style={styles.advance}>
          {paywalled ? (
            <Button label="Go Pro to continue" variant="premium" size="sm" onPress={onGoPro} />
          ) : (
            <Button
              label={game.phase === 'playoffs' ? 'Play round' : `Advance ${state.label}`}
              loading={advancing}
              disabled={state.blocked}
              onPress={tapAdvance}
            />
          )}
        </View>
      </View>
      <AppText style={styles.srOnly} accessibilityElementsHidden importantForAccessibility="no">
        {simAdvanceLabel(game)}
      </AppText>
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    bar: {
      position: 'absolute',
      left: spacing.md,
      right: spacing.md,
      paddingVertical: spacing.sm,
      paddingHorizontal: spacing.md,
      gap: spacing.xs,
      borderRadius: radii.lg,
      borderWidth: 1,
      borderColor: colors.border,
      backgroundColor: colors.backgroundElevated,
      zIndex: 5,
    },
    row: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: spacing.md },
    advance: { flex: 1, alignItems: 'flex-end' },
    reason: { fontSize: 12, fontWeight: '700', color: colors.warning, textAlign: 'center' },
    pill: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: spacing.xs,
      minHeight: 44,
      paddingHorizontal: spacing.md,
      borderRadius: radii.pill,
      borderWidth: 1,
      borderColor: colors.borderStrong ?? colors.border,
    },
    pillOff: { opacity: 0.6 },
    pillLabel: { fontSize: 13, fontWeight: '700', color: colors.textPrimary },
    srOnly: { height: 0, width: 0, opacity: 0 },
  });
}
