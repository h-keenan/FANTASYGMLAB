import React, { useEffect, useMemo, useState } from 'react';
import { Alert, StyleSheet, View } from 'react-native';

import AppText from './AppText';
import Button from './Button';
import type { SimCtx } from './SimGameParts';
import { useThemeMode } from '../context/ThemeModeContext';
import { api } from '../lib/api';
import { simAdvanceLabel } from '../lib/simGame';
import { simAdvanceState, simLineupIssues, type SimZeroStarter } from '../lib/simLayout';
import { radii, spacing, type ThemeColors } from '../theme';

/**
 * The persistent bottom action bar for the in-season tabs (mirrors web-next's
 * SimActionBar): Advance week ("Week 4 -> 5", disabled only when a cut is owed;
 * an empty slot warns and asks to confirm). ADVANCE ONLY: Auto-set lives on Home,
 * "What to do this week". An in-flow glass pill: the screen's bottom stack docks
 * it at the bottom with the game orb right above it, and pads the content to match.
 */
export default function SimActionBar({ ctx, paywalled, advancing, onAdvance, onSimTo, onGoPro, onTab }: { ctx: SimCtx; paywalled: boolean; advancing: boolean; onAdvance: () => void; onSimTo?: () => void; onGoPro: () => void; onTab?: (tab: 'team' | 'players') => void }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const { gameId, game } = ctx;
  const [issues, setIssues] = useState<{ empty: string[]; zero: SimZeroStarter[] }>({ empty: [], zero: [] });

  useEffect(() => {
    let cancelled = false;
    api
      .getSimLineup(gameId)
      .then((body) => {
        if (!cancelled) setIssues(simLineupIssues(body.slots ?? [], body.warnings ?? []));
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [gameId, ctx.tick, game]);

  const state = simAdvanceState(game, issues.empty, issues.zero);
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
    <View style={styles.bar} testID="sim-action-bar">
      {state.warning && !state.reason && !paywalled ? <AppText style={styles.reason}>{state.warning}</AppText> : null}
      {state.reason && !paywalled ? (
        <AppText style={styles.reason} accessibilityRole="alert">
          {state.reason}
        </AppText>
      ) : null}
      <View style={styles.row}>
        {onSimTo && !paywalled ? <Button label="Sim to..." variant="secondary" size="sm" disabled={advancing} onPress={onSimTo} /> : null}
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
      paddingVertical: spacing.sm,
      paddingHorizontal: spacing.md,
      gap: spacing.xs,
      borderRadius: radii.lg,
      borderWidth: 1,
      borderColor: colors.border,
      backgroundColor: colors.backgroundElevated,
    },
    row: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: spacing.md },
    advance: { flex: 1 },
    reason: { fontSize: 12, fontWeight: '700', color: colors.warning, textAlign: 'center' },
    srOnly: { height: 0, width: 0, opacity: 0 },
  });
}
