import React, { useEffect, useMemo, useState } from 'react';
import { createShareToggleFlow, type ShareToggleFlow } from '../lib/shareToggleFlow';
import { StyleSheet, View } from 'react-native';

import AppText from './AppText';
import Button from './Button';
import { api } from '../lib/api';
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
  // Serializes share and off so that switching off during an in-flight share always wins.

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

  const [flow] = useState<ShareToggleFlow>(() =>
    createShareToggleFlow({ unshare: async (id) => (await api.deleteSharedCommunityTrade(id))?.ok !== false }),
  );

  if (!available || !isShareableGrade(verdict.ui_verdict)) return null;

  const sendShare = async () => {
    const result = await api.shareCommunityTrade(buildShareBody(verdict, send, receive, name));
    return result.ok && result.trade ? result.trade.id : null;
  };

  const share = async () => {
    setBusy(true);
    setError('');
    try {
      const outcome = await flow.requestShare(sendShare);
      if (outcome === 'shared') setSharedId(flow.sharedId);
      else if (outcome === 'unavailable') setError("Sharing isn't available right now.");
      else if (outcome === 'error') setError('Could not share this trade.');
      else if (outcome === 'stuck-public') {
        setOn(true);
        setSharedId(flow.sharedId);
        setError('Could not stop sharing this trade. Try again.');
      }
    } finally {
      setBusy(false);
    }
  };

  const onToggle = (next: boolean) => {
    if (next) {
      setOn(true);
      return;
    }
    setOn(false);
    setSharedId(null);
    setError('');
    // A failed delete must not leave the switch saying "off" while the trade is still public.
    void flow.requestOff().then((outcome) => {
      if (outcome === 'still-public') {
        setOn(true);
        setSharedId(flow.sharedId);
        setError('Could not stop sharing this trade. Try again.');
      }
    });
  };

  return (
    <View style={styles.box}>
      <View style={styles.row}>
        <AppText style={styles.label}>Share to community</AppText>
        <Toggle value={on} onValueChange={onToggle} label="Share to community" />
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
    label: { fontSize: 15.5, color: colors.textSecondary },
    form: { gap: spacing.sm },
    input: {
      borderWidth: 1,
      borderColor: colors.cardBorder,
      borderRadius: radii.sm,
      paddingHorizontal: spacing.md,
      paddingVertical: 10,
      fontSize: 16.5,
      backgroundColor: colors.surface,
      color: colors.textPrimary,
    },
    hint: { fontSize: 13.5, color: colors.textTertiary },
  });
}
