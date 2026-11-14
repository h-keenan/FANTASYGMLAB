import ConfirmInPlace from './ConfirmInPlace';
import React, { useMemo, useState } from 'react';
import { ActivityIndicator, StyleSheet, View } from 'react-native';
import PressableScale from './PressableScale';

import AppText from './AppText';
import Input from './Input';
import { useThemeMode } from '../context/ThemeModeContext';
import { ApiError, api } from '../lib/api';
import { ESPN_COOKIE_STEPS, ESPN_LOGIN_WHY, espnCredentialFailureMessage } from '../lib/leaguePlatform';
import { radii, spacing, type ThemeColors } from '../theme';

/**
 * Connect an ESPN login (espn_s2 + SWID) so private ESPN leagues can be read.
 * Mirrors web-next's EspnLoginPanel. The values are sent once to
 * POST /v1/espn/credentials and never shown back; with a league id + season
 * the server proves them on that league first and saves nothing on failure.
 */
export function EspnLoginPanel({
  leagueId,
  season,
  onConnected,
}: {
  leagueId?: string;
  season?: number;
  onConnected: () => void;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [espnS2, setEspnS2] = useState('');
  const [swid, setSwid] = useState('');
  const [busy, setBusy] = useState(false);
  const [showSteps, setShowSteps] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const submit = async () => {
    if (!espnS2.trim() || !swid.trim()) {
      setMessage('Paste both espn_s2 and SWID.');
      return;
    }
    setBusy(true);
    setMessage(null);
    try {
      const result = await api.saveEspnCredentials({ espnS2, swid, leagueId, season });
      if (!result?.ok) {
        setMessage(espnCredentialFailureMessage(result));
        return;
      }
      setEspnS2('');
      setSwid('');
      onConnected();
    } catch (error) {
      setMessage(error instanceof ApiError ? error.message : 'Could not reach the FantasyDesk API.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <View>
      <AppText style={styles.title}>This league is private. Connect your ESPN login to read it.</AppText>
      <AppText style={styles.hint}>{ESPN_LOGIN_WHY}</AppText>
      <PressableScale onPress={() => setShowSteps((value) => !value)} accessibilityRole="button" hitSlop={8}>
        <AppText style={styles.link}>{showSteps ? 'Hide steps' : 'How to find espn_s2 and SWID'}</AppText>
      </PressableScale>
      {showSteps ? (
        <View style={styles.steps}>
          {ESPN_COOKIE_STEPS.map((step, index) => (
            <AppText key={step} style={styles.hint}>
              {index + 1}. {step}
            </AppText>
          ))}
        </View>
      ) : null}
      <AppText style={styles.kicker}>espn_s2</AppText>
      <Input
        value={espnS2}
        onChangeText={setEspnS2}
        secureTextEntry
        autoCapitalize="none"
        autoCorrect={false}
        editable={!busy}
        accessibilityLabel="espn_s2"
      />
      <AppText style={styles.kicker}>SWID</AppText>
      <Input
        value={swid}
        onChangeText={setSwid}
        placeholder="{XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX}"
        autoCapitalize="none"
        autoCorrect={false}
        editable={!busy}
        accessibilityLabel="SWID"
      />
      {message ? <AppText style={styles.error}>{message}</AppText> : null}
      <PressableScale style={styles.primaryButton} disabled={busy} onPress={() => void submit()}>
        {busy ? (
          <ActivityIndicator size="small" color={colors.onAccent} />
        ) : (
          <AppText style={styles.primaryText}>{leagueId ? 'Test on my league and connect' : 'Save ESPN login'}</AppText>
        )}
      </PressableScale>
    </View>
  );
}

/** One line: "ESPN login connected" + Remove. Renders nothing until a login is saved. */
export function EspnLoginStatus({ saved, onRemoved }: { saved: boolean; onRemoved: () => void }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  if (!saved) return null;
  const remove = async (): Promise<boolean> => {
    setBusy(true);
    setMessage(null);
    try {
      const result = await api.deleteEspnCredentials();
      if (result?.ok) {
        onRemoved();
        return true;
      }
      setMessage(espnCredentialFailureMessage(result));
      return false;
    } catch (error) {
      setMessage(error instanceof ApiError ? error.message : 'Could not reach the FantasyDesk API.');
      return false;
    } finally {
      setBusy(false);
    }
  };
  return (
    <View style={styles.statusRow}>
      <AppText style={styles.hint}>ESPN login connected (private leagues can load).</AppText>
      <ConfirmInPlace
        variant="row"
        mode="ask"
        label="Remove ESPN login"
        prompt="Remove your ESPN login?"
        confirmLabel="Remove"
        errorText="Could not remove it. Try again."
        disabled={busy}
        onConfirm={remove}
      />
      {message ? <AppText style={styles.error}>{message}</AppText> : null}
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    title: { fontSize: 15.5, fontWeight: '700', color: colors.textPrimary, marginBottom: spacing.xs },
    hint: { fontSize: 13.5, color: colors.textSecondary, lineHeight: 19, marginBottom: spacing.xs },
    link: { fontSize: 14.5, fontWeight: '700', color: colors.accent },
    steps: { marginTop: spacing.sm },
    kicker: { fontSize: 12.5, fontWeight: '700', textTransform: 'uppercase', color: colors.textTertiary, marginTop: spacing.sm, marginBottom: spacing.xs },
    error: { fontSize: 13.5, color: colors.danger, marginTop: spacing.sm, lineHeight: 18 },
    primaryButton: {
      backgroundColor: colors.accent,
      paddingHorizontal: spacing.lg,
      paddingVertical: 10,
      borderRadius: radii.sm,
      alignItems: 'center',
      marginTop: spacing.md,
    },
    primaryText: { fontSize: 15.5, fontWeight: '700', color: colors.onAccent },
    statusRow: { marginBottom: spacing.sm },
  });
}
