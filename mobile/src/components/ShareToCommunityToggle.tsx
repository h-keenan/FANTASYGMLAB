import React, { useEffect, useMemo, useState } from 'react';
import { StyleSheet, View } from 'react-native';

import AppText from './AppText';
import Button from './Button';
import { api } from '../lib/api';
import { toUserErrorMessage } from '../lib/errorMessages';
import { buildShareBody, isShareableGrade, SHARE_NAME_MAX, type ShareableVerdict, type SharedTradeAssetInput } from '../lib/sharedTrades';
import { useThemeMode } from '../context/ThemeModeContext';
import { radii, spacing, type ThemeColors } from '../theme';
import Input from './Input';
import Toggle from './Toggle';

/**
 * Opt-in "Share to community" for a Trade Analyzer result (mirrors web-next
 * ShareToCommunityToggle). Off by default; nothing is sent until the user
 * flips it on and presses Share. Hidden when storage is not set up.
 */
export default function ShareToCommunityToggle({
  verdict,
  send,
  receive,
}: {
  verdict: ShareableVerdict;
  send: SharedTradeAssetInput[];
  receive: SharedTradeAssetInput[];
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [available, setAvailable] = useState(false);
  const [on, setOn] = useState(false);
  const [name, setName] = useState('');
  const [busy, setBusy] = useState(false);
  const [sharedId, setSharedId] = useState<string | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    api
      .getSharedCommunityTrades(1)
      .then((result) => {
        if (!cancelled) setAvailable(Boolean(result.available));
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  if (!available || !isShareableGrade(verdict.ui_verdict)) return null;

  const share = async () => {
    setBusy(true);
    setError('');
    try {
      const result = await api.shareCommunityTrade(buildShareBody(verdict, send, receive, name));
      if (result.ok && result.trade) setSharedId(result.trade.id);
      else setError("Sharing isn't available right now.");
    } catch (err) {
      setError(toUserErrorMessage(err, 'Could not share this trade.'));
    } finally {
      setBusy(false);
    }
  };

  const onToggle = (next: boolean) => {
    if (next) {
      setOn(true);
      return;
    }
    const id = sharedId;
    setOn(false);
    setSharedId(null);
    setError('');
    if (id) void api.deleteSharedCommunityTrade(id).catch(() => {});
  };

  return (
    <View style={styles.box}>
      <View style={styles.row}>
        <AppText style={styles.label}>Share to community</AppText>
        <Toggle value={on} onValueChange={onToggle} disabled={busy} label="Share to community" />
      </View>
      {on && !sharedId ? (
        <View style={styles.form}>
          <Input
            value={name}
            onChangeText={setName}
            maxLength={SHARE_NAME_MAX}
            placeholder="Display name (optional)"
            accessibilityLabel="Display name (optional)"
          />
          <AppText style={styles.hint}>Shows the assets, grade and reason. Blank is Anonymous.</AppText>
          <Button label="Share" onPress={() => void share()} loading={busy} />
        </View>
      ) : null}
      {sharedId ? <AppText style={[styles.hint, { color: colors.success }]}>Shared. Turn off to remove it.</AppText> : null}
      {error ? <AppText style={[styles.hint, { color: colors.danger }]}>{error}</AppText> : null}
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    box: { borderWidth: 1, borderColor: colors.cardBorder, borderRadius: radii.sm, padding: spacing.md, gap: spacing.sm, marginTop: spacing.sm },
    row: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: spacing.sm },
    label: { fontSize: 14, color: colors.textSecondary },
    form: { gap: spacing.sm },
    input: {
      borderWidth: 1,
      borderColor: colors.cardBorder,
      borderRadius: radii.sm,
      paddingHorizontal: spacing.md,
      paddingVertical: 10,
      fontSize: 15,
      backgroundColor: colors.surface,
      color: colors.textPrimary,
    },
    hint: { fontSize: 12, color: colors.textTertiary },
  });
}
