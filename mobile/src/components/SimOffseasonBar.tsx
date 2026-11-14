import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { StyleSheet, View } from 'react-native';

import AppText from './AppText';
import BottomPill from './BottomPill';
import Button from './Button';
import type { SimCtx } from './SimGameParts';
import { useThemeMode } from '../context/ThemeModeContext';
import { api } from '../lib/api';
import { usePillState } from '../lib/useBottomPillContext.ts';
import { simTabAfterStageAction, type SimStageAction } from '../lib/simScroll';
import { simOffseasonCta, simOffseasonStageLabel, simSeasonLabel, type SimOffseason, type SimOffseasonResponse } from '../lib/simGame';
import { BAR_METRICS } from '../lib/bottomBarMetrics';
import { radii, spacing, type ThemeColors } from '../theme';

/**
 * The one persistent primary action for every offseason tab (Offseason, Team,
 * Trades, League), mirroring web-next's SimOffseasonBar: Start rookie draft,
 * Auto-draft the rest (asks first), Start season N ("Finish cut-down",
 * disabled with the reason, only in saves from before the soft roster limit; newer saves show a compact over-the-limit note and can start over the limit). It reads the
 * offseason itself so any tab can mount it. An in-flow glass pill like
 * SimActionBar: the screen's bottom stack docks it with the game orb above it.
 */
export default function SimOffseasonBar({ ctx, onTab, orb }: { ctx: SimCtx; onTab?: (tab: 'home') => void; orb?: React.ReactNode }) {
  const pill = usePillState();
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const { gameId, call } = ctx;
  const [off, setOff] = useState<SimOffseason | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirmAuto, setConfirmAuto] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api
      .getSimOffseason(gameId, '')
      .then((body) => {
        if (!cancelled && body.offseason) setOff(body.offseason);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [gameId, ctx.tick]);

  const run = useCallback(
    async (fn: () => Promise<SimOffseasonResponse>, message?: (body: SimOffseasonResponse) => string, action?: SimStageAction) => {
      setBusy(true);
      const body = await call(fn);
      setBusy(false);
      if (body) {
        if (body.offseason) setOff(body.offseason);
        if (body.game) ctx.setGame(body.game);
        ctx.bump();
        if (action) onTab?.(simTabAfterStageAction(action));
        const text = message?.(body);
        if (text) ctx.notify(text, 'success');
      }
    },
    [call, ctx, onTab],
  );

  if (!off) return null;
  const cta = simOffseasonCta(off);

  function press() {
    if (!off) return;
    if (off.stage === 'review') {
      void run(() => api.startSimRookieDraft(gameId), (b) => ((b.made?.length ?? 0) > 0 ? `${b.made?.length} AI picks made. You are up.` : ''), 'start_rookie_draft');
    } else if (off.stage === 'rookie_draft') {
      setConfirmAuto(true);
    } else {
      void run(async () => (await api.startSimSeason(gameId)) as SimOffseasonResponse, () => `${off.season_label || simSeasonLabel(off.season_no + 1, off.year)} is on.`, 'start_season');
    }
  }

  return (
    <View style={styles.bar} testID="sim-offseason-bar">
      {off.stage === 'rookie_draft' && confirmAuto ? (
        <View style={{ gap: spacing.sm }}>
          <AppText style={styles.confirm} accessibilityRole="alert">
            Auto-draft makes every one of your remaining picks for you, best available by your needs.
          </AppText>
          <View style={styles.row}>
            <Button
              size="sm"
              label="Auto-draft the rest"
              loading={busy}
              onPress={() => {
                setConfirmAuto(false);
                void run(() => api.autoSimRookieDraft(gameId), () => 'The rookie draft is done.', 'auto_draft');
              }}
            />
            <Button size="sm" variant="ghost" label="Keep drafting" onPress={() => setConfirmAuto(false)} />
          </View>
        </View>
      ) : null}
      {cta.note ? (
        <AppText style={styles.reason} testID="offseason-over-note">
          {cta.note}
        </AppText>
      ) : null}
      {cta.blocked ? (
        <AppText style={styles.reason} accessibilityRole="alert">
          {cta.blocked}
        </AppText>
      ) : null}
      <BottomPill bare context={pill.barPresent ? pill.ctx : null}>
        <View style={styles.row}>
        {orb}
        <View style={[styles.cta, cta.blocked ? styles.ctaBlocked : null]}>
          <Button label={cta.label} loading={busy && !confirmAuto} disabled={Boolean(cta.blocked) || confirmAuto} onPress={press} />
        </View>
        </View>
      </BottomPill>
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
    row: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: spacing.md },
    step: { flex: 1, minWidth: 0, fontSize: 12.5, fontWeight: '700', color: colors.textTertiary },
    cta: { flex: 1, minWidth: 0 },
    ctaBlocked: { borderWidth: 1, borderColor: colors.borderStrong ?? colors.border, borderRadius: radii.md },
    reason: { fontSize: 12, fontWeight: '700', color: colors.warning, textAlign: 'center' },
    confirm: { fontSize: 14, color: colors.textPrimary },
  });
}
