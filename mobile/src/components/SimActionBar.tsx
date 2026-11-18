import React, { useEffect, useMemo, useState } from 'react';
import { Alert, Pressable, StyleSheet, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import AppText from './AppText';
import TabIcon from './TabIcon';
import BottomPill from './BottomPill';
import Button from './Button';
import type { SimCtx } from './SimGameParts';
import { useThemeMode } from '../context/ThemeModeContext';
import { api } from '../lib/api';
import { usePillState } from '../lib/useBottomPillContext.ts';
import { isSelectionAction, simAdvanceChip, simFooterTabs, simPillPlan, type PillContext, type PillContextAction } from '../lib/bottomNav';
import type { SimTab } from '../lib/simGameFlow';
import { shortPlayerName } from '../lib/playerNameDisplay';
import { simAdvanceLabel } from '../lib/simGame';
import { simAdvanceState, simLineupIssues, type SimZeroStarter } from '../lib/simLayout';
import { BAR_METRICS } from '../lib/bottomBarMetrics';
import { radii, spacing, type ThemeColors } from '../theme';

/**
 * The persistent bottom action bar for the in-season tabs (mirrors web-next's
 * SimActionBar): Advance week ("Week 4 -> 5", disabled only when a cut is owed;
 * an empty slot warns and asks to confirm). ADVANCE ONLY: Auto-set lives on Home,
 * "What to do this week". An in-flow glass pill: the screen's bottom stack docks
 * it at the bottom with the game orb inside its one row (orb | Sim to or a page action | Advance), and pads the content to match.
 */
export default function SimActionBar({ ctx, paywalled, advancing, onAdvance, onSimTo, onGoPro, onTab, orb, tab }: { ctx: SimCtx; paywalled: boolean; advancing: boolean; onAdvance: () => void; onSimTo?: () => void; onGoPro: () => void; onTab?: (tab: SimTab) => void; orb?: React.ReactNode; /** The lit page (Home / Team / ...). */ tab?: string }) {
  const pill = usePillState();
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

  const plan = simPillPlan({ context: pill.barPresent ? pill.ctx : null, simToAvailable: Boolean(onSimTo), paywalled });
  const state = simAdvanceState(game, issues.empty, issues.zero);
  // An empty slot is a warning, not a block: confirm, with shortcuts to fix it first.
  const tapAdvance = () => {
    if (!state.confirm) {
      onAdvance();
      return;
    }
    // Concept A: the amber "Set lineup" chip opens this confirm (web twin: the "Set your lineup first?" sheet). Fix now goes to the Team page's
    // lineup (Auto-set lives there), Play anyway keeps the old "Advance anyway" guard.
    Alert.alert('Set your lineup first?', issues.zero.reduce((t, z) => t.split(z.name).join(shortPlayerName(z.name)), state.confirm.replace(/ Advance anyway\?$/, '')), [
      { text: 'Cancel', style: 'cancel' },
      ...(onTab ? [{ text: 'Fix now', onPress: () => onTab('team') }] : []),
      { text: 'Play anyway', style: 'destructive' as const, onPress: onAdvance },
    ]);
  };
  // Concept A: orb | Home / Team / Players / Trades | ONE chip (amber "⚠ 1 · Set lineup" when starters will score 0). A page's selection
  // submit ("3 selected · Claim") takes the chip and the tabs step aside.
  const issueCount = issues.empty.length + issues.zero.length;
  const chip = simAdvanceChip({ phase: game.phase, week: game.week, issues: state.confirm ? issueCount : 0 });
  const selection = pill.barPresent && isSelectionAction(pill.ctx?.primary) ? pill.ctx?.primary ?? null : null;
  const primary: PillContextAction = selection ?? (paywalled
    ? { key: 'go-pro', label: 'Go Pro', onPress: onGoPro }
    : { key: 'advance', label: chip.label, tone: chip.warn ? 'warning' : undefined, busy: advancing, disabled: state.blocked, onPress: tapAdvance });
  const phoneSegment: PillContext | null = pill.barPresent
    ? { id: selection ? 'sim-selection' : 'sim-season', label: 'Fantasy Sim pages', tabs: selection ? [] : simFooterTabs({ chipLabel: primary.label }), activeKey: tab ?? 'home', onSelect: (key) => onTab?.(key as SimTab), primary }
    : null;
  return (
    <View style={styles.bar} testID="sim-action-bar">
      {/* No standing "will score 0" line here (web's phone pill hides it too): it came and went with every lineup refetch, resizing the pill
          around each Advance. The same text is shown once, in the confirm Alert, when Advance is tapped. */}
      {state.reason && !paywalled ? (
        <AppText style={styles.reason} accessibilityRole="alert">
          {state.reason}
        </AppText>
      ) : null}
      <BottomPill bare segment={phoneSegment ?? plan.segment} orb={orb}>
      <View style={styles.row}>
        {plan.simTo && onSimTo ? (
          <Pressable onPress={onSimTo} disabled={advancing} accessibilityRole="button" accessibilityLabel="Sim to..." style={[styles.simTo, advancing && { opacity: 0.5 }]} testID="sim-to-button">
            <Ionicons name="play-forward-outline" size={18} color={colors.textPrimary} />
            <AppText style={styles.simToLabel}>Sim to</AppText>
          </Pressable>
        ) : null}
        {plan.inlineAction ? (
          <Pressable onPress={plan.inlineAction.onPress} disabled={plan.inlineAction.disabled || plan.inlineAction.busy} accessibilityRole="button" accessibilityLabel={plan.inlineAction.label} style={[styles.inline, (plan.inlineAction.disabled || plan.inlineAction.busy) && { opacity: 0.5 }]} testID="pill-inline-action">
            {plan.inlineAction.glyph ? <TabIcon name={plan.inlineAction.glyph} color={colors.textPrimary} size={16} /> : null}
            <AppText style={styles.simToLabel} numberOfLines={1}>{plan.inlineAction.label}</AppText>
          </Pressable>
        ) : null}
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
      </BottomPill>
      <AppText style={styles.srOnly} accessibilityElementsHidden importantForAccessibility="no">
        {simAdvanceLabel(game)}
      </AppText>
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    bar: {
      // The shared floating glass pill (BottomPill / web .action-pill): translucent glass fill, lit rim, capsule radius.
      paddingVertical: BAR_METRICS.pillPadding,
      paddingHorizontal: BAR_METRICS.pillPadding + spacing.xs,
      gap: spacing.xs,
      borderRadius: 28,
      borderWidth: 1,
      borderColor: colors.glassBorder,
      backgroundColor: colors.glass,
      shadowColor: '#000',
      shadowOpacity: 0.4,
      shadowRadius: 12,
      shadowOffset: { width: 0, height: 6 },
      elevation: 6,
    },
    row: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: spacing.md },
    advance: { flex: 1, minWidth: 0 },
    simToLabel: { fontSize: 12, lineHeight: 14, fontWeight: '700', color: colors.textSecondary },
    inline: { minWidth: 44, height: 48, paddingHorizontal: 12, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, borderRadius: radii.pill, borderWidth: 1, borderColor: colors.borderStrong ?? colors.border },
    simTo: { minWidth: 52, height: 48, paddingHorizontal: 6, alignItems: 'center', justifyContent: 'center', borderRadius: radii.pill, borderWidth: 1, borderColor: colors.borderStrong ?? colors.border },
    reason: { fontSize: 12, fontWeight: '700', color: colors.warning, textAlign: 'center' },
    srOnly: { height: 0, width: 0, opacity: 0 },
  });
}
