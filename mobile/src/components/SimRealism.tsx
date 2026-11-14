import React, { useEffect, useMemo, useState } from 'react';
import { StyleSheet, View } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';

import AccentCard from './AccentCard';
import AppText from './AppText';
import Button from './Button';
import CompactModule from './CompactModule';
import { SimSheet, type SimCtx } from './SimGameParts';
import ToneBadge from './ToneBadge';
import { useThemeMode } from '../context/ThemeModeContext';
import { api } from '../lib/api';
import {
  SIM_REALISM_BANNER_DISMISS,
  SIM_REALISM_CANCEL_LABEL,
  SIM_REALISM_CONFIRM_LABEL,
  SIM_REALISM_CURRENT,
  SIM_REALISM_INTRO,
  SIM_REALISM_MENU_TITLE,
  SIM_REALISM_NOT_RETROACTIVE,
  SIM_REALISM_SHEET_DESCRIPTION,
  SIM_REALISM_SHEET_TITLE,
  SIM_REALISM_UNDO_NOTE,
  simRealismBanner,
  simRealismBannerKey,
  simRealismGroups,
  simRealismParts,
  simRealismPending,
  simRealismToast,
  simRealismWhen,
} from '../lib/simRealism';
import { spacing, type ThemeColors } from '../theme';

/**
 * The Realism update: confirm sheet, More / Game menu entry and the one-time Home banner for a save made before newer rules.
 * Twin of web-next's SimRealism. The server appends one event to the game's log; past results never change.
 */
export function SimRealismSheet({ ctx, onClose }: { ctx: SimCtx; onClose: () => void }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [busy, setBusy] = useState(false);
  const pending = simRealismPending(ctx.game);
  const groups = simRealismGroups(pending);

  async function confirm() {
    if (busy) return;
    setBusy(true);
    try {
      const body = await ctx.call(() => api.realismUpgradeSimGame(ctx.gameId));
      if (!body) return;
      ctx.setGame({ ...ctx.game, settings: body.settings ?? ctx.game.settings, rules: body.rules ?? ctx.game.rules });
      ctx.bump();
      ctx.notify(simRealismToast(body), 'success');
      onClose();
    } finally {
      setBusy(false);
    }
  }

  return (
    <SimSheet title={SIM_REALISM_SHEET_TITLE} onClose={onClose}>
      <View style={styles.stack} testID="sim-realism-sheet">
        <AppText style={styles.muted}>{SIM_REALISM_SHEET_DESCRIPTION}</AppText>
        <AppText style={styles.body}>{SIM_REALISM_INTRO}</AppText>
        {groups.length === 0 ? (
          <AppText style={styles.bodyStrong}>{SIM_REALISM_CURRENT}</AppText>
        ) : (
          groups.map((g) => (
            <View key={g.boundary} style={styles.stack} accessibilityLabel={g.when}>
              <ToneBadge label={g.when} color={colors.accent} size="xs" />
              {g.flags.map((f) => (
                <View key={f.flag} style={styles.tight} testID={`sim-realism-flag-${f.flag}`}>
                  <AppText style={styles.bodyStrong}>{f.label}</AppText>
                  <AppText style={styles.body}>{f.body}</AppText>
                </View>
              ))}
            </View>
          ))
        )}
        <AppText style={styles.bodyStrong} testID="sim-realism-note">{SIM_REALISM_NOT_RETROACTIVE}</AppText>
        <AppText style={styles.muted}>{SIM_REALISM_UNDO_NOTE}</AppText>
        <View style={styles.row}>
          <Button size="sm" variant="secondary" label={SIM_REALISM_CANCEL_LABEL} onPress={onClose} disabled={busy} />
          <Button size="sm" label={busy ? 'Updating...' : SIM_REALISM_CONFIRM_LABEL} onPress={confirm} disabled={busy || pending.length === 0} />
        </View>
      </View>
    </SimSheet>
  );
}

/** The More / Game menu entry: the explanation, the status, and the button that opens the confirm sheet. */
export function SimRealismModule({ ctx }: { ctx: SimCtx }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [open, setOpen] = useState(false);
  const info = ctx.game.rules;
  if (!info) return null;
  const pending = simRealismPending(ctx.game);
  return (
    <>
      <CompactModule id="sim.menu.realism" testID="sim-realism-module" title={SIM_REALISM_MENU_TITLE} parts={simRealismParts(info)} tone={pending.length > 0 ? 'accent' : 'muted'} persist={false}>
        <AppText style={styles.body}>{pending.length > 0 ? SIM_REALISM_INTRO : SIM_REALISM_CURRENT}</AppText>
        {pending.map((f) => (
          <AppText key={f.flag} style={styles.body}>
            <AppText style={styles.bodyStrong}>{f.label}</AppText> ({simRealismWhen(f).toLowerCase()})
          </AppText>
        ))}
        {info.scheduled.length > 0 ? <AppText style={styles.muted}>Starting next offseason: {info.scheduled.map((f) => f.label).join(', ')}.</AppText> : null}
        <AppText style={styles.muted}>{SIM_REALISM_NOT_RETROACTIVE}</AppText>
        {pending.length > 0 ? <Button size="sm" variant="secondary" label="Review and update" onPress={() => setOpen(true)} style={styles.start} /> : null}
      </CompactModule>
      {open ? <SimRealismSheet ctx={ctx} onClose={() => setOpen(false)} /> : null}
    </>
  );
}

/** A compact, dismissible one-time banner on Home for an old save with at least one rule off. */
export function SimRealismBanner({ ctx }: { ctx: SimCtx }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const key = simRealismBannerKey(ctx.gameId, ctx.game.rules);
  const [dismissed, setDismissed] = useState(true); // hidden until the stored answer is known: no flash for a user who dismissed it
  const [open, setOpen] = useState(false);
  useEffect(() => {
    let cancelled = false;
    AsyncStorage.getItem(key)
      .then((v) => {
        if (!cancelled) setDismissed(v === '1');
      })
      .catch(() => {
        if (!cancelled) setDismissed(false);
      });
    return () => {
      cancelled = true;
    };
  }, [key]);
  const banner = simRealismBanner(ctx.game, dismissed);
  if (!banner) return null;
  return (
    <>
      <AccentCard accent={colors.accent} compact>
        <View style={styles.row} testID="sim-realism-banner">
          <View style={styles.grow}>
            <AppText style={styles.bodyStrong}>{banner.title}</AppText>
            <AppText style={styles.muted}>{banner.body}</AppText>
          </View>
          <Button size="sm" label={banner.cta} onPress={() => setOpen(true)} />
          <Button
            size="sm"
            variant="secondary"
            label={SIM_REALISM_BANNER_DISMISS}
            onPress={() => {
              setDismissed(true);
              AsyncStorage.setItem(key, '1').catch(() => undefined);
            }}
          />
        </View>
      </AccentCard>
      {open ? <SimRealismSheet ctx={ctx} onClose={() => setOpen(false)} /> : null}
    </>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    stack: { gap: spacing.sm },
    tight: { gap: 2 },
    row: { flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', gap: spacing.sm },
    grow: { flex: 1, minWidth: 160 },
    start: { alignSelf: 'flex-start' },
    body: { fontSize: 15, lineHeight: 21, color: colors.textSecondary },
    bodyStrong: { fontSize: 15, fontWeight: '700', color: colors.textPrimary },
    muted: { fontSize: 13, lineHeight: 18, color: colors.textTertiary },
  });
}
