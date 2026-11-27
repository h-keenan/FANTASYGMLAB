import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { StyleSheet, View } from 'react-native';
import * as WebBrowser from 'expo-web-browser';

import AppText from './AppText';
import PressableScale from './PressableScale';
import { SkeletonRows } from './Skeleton';
import { useThemeMode } from '../context/ThemeModeContext';
import { api, ApiError, type YahooLeagueOption } from '../lib/api';
import { radii, spacing, typography, type ThemeColors } from '../theme';
import {
  YAHOO_CONNECT_LABEL,
  YAHOO_NO_LEAGUES,
  YAHOO_PICK_HEADING,
  YAHOO_UNAVAILABLE,
  YAHOO_WHY,
  parseYahooReturn,
  yahooNeedsConnect,
  yahooReasonMessage,
} from '../lib/yahooConnect';

/** Where the API callback sends the app after Yahoo's sign-in (modules/yahoo_connect.py APP_RETURN_URL). */
const YAHOO_APP_RETURN = 'fantasygmlab://yahoo';

type Phase = 'checking' | 'unavailable' | 'connect' | 'loading' | 'pick';

/**
 * Yahoo half of the Add League sheet (EspnLeagueImport platform="yahoo"); web twin: components/YahooConnectStep.tsx.
 * Yahoo has no league-ID lookup: the user signs in with Yahoo in the system browser sheet (OAuth through the API
 * callback, which redirects to fantasygmlab://yahoo?status=...), then picks a league from their own list. `onPick`
 * hands the chosen league to the shared preview -> team -> save flow.
 */
export default function YahooConnectStep({ onPick, disabled }: { onPick: (league: YahooLeagueOption) => void; disabled?: boolean }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [phase, setPhase] = useState<Phase>('checking');
  const [message, setMessage] = useState<string | null>(null);
  const [leagues, setLeagues] = useState<YahooLeagueOption[]>([]);
  const [busy, setBusy] = useState(false);

  const loadLeagues = useCallback(async () => {
    setPhase('loading');
    try {
      const result = await api.listYahooLeagues();
      if (!result.ok) {
        setMessage(yahooReasonMessage(result.reason, result.message));
        setLeagues([]);
        setPhase(yahooNeedsConnect(result.reason) ? 'connect' : 'pick');
        return;
      }
      setLeagues(result.leagues ?? []);
      setPhase('pick');
    } catch (error) {
      setMessage(error instanceof ApiError ? error.message : yahooReasonMessage('yahoo_unavailable'));
      setPhase('pick');
    }
  }, []);

  useEffect(() => {
    let live = true;
    api
      .getYahooStatus()
      .then((status) => {
        if (!live) return;
        if (!status.ok || !status.available) setPhase('unavailable');
        else if (status.connected) void loadLeagues();
        else setPhase('connect');
      })
      .catch(() => live && setPhase('unavailable'));
    return () => {
      live = false;
    };
  }, [loadLeagues]);

  const connect = async () => {
    setBusy(true);
    setMessage(null);
    try {
      const start = await api.startYahooOAuth('app');
      if (!start.ok || !start.authorize_url) {
        setMessage(yahooReasonMessage(start.reason, start.message));
        return;
      }
      const result = await WebBrowser.openAuthSessionAsync(start.authorize_url, YAHOO_APP_RETURN);
      if (result.type !== 'success') return; // closed the sheet: stay on Connect
      const returned = parseYahooReturn(result.url);
      if (returned?.connected) await loadLeagues();
      else setMessage(yahooReasonMessage(returned?.reason ?? 'exchange_failed'));
    } catch (error) {
      setMessage(error instanceof ApiError ? error.message : yahooReasonMessage('yahoo_unavailable'));
    } finally {
      setBusy(false);
    }
  };

  const disconnect = async () => {
    setBusy(true);
    try {
      const result = await api.disconnectYahoo();
      if (result.ok) {
        setLeagues([]);
        setMessage(null);
        setPhase('connect');
      } else {
        setMessage(yahooReasonMessage(result.reason, result.message));
      }
    } catch (error) {
      setMessage(error instanceof ApiError ? error.message : yahooReasonMessage('yahoo_unavailable'));
    } finally {
      setBusy(false);
    }
  };

  if (phase === 'checking' || phase === 'loading') {
    return <SkeletonRows count={2} />;
  }
  if (phase === 'unavailable') {
    return <AppText style={styles.error}>{YAHOO_UNAVAILABLE}</AppText>;
  }
  if (phase === 'connect') {
    return (
      <View testID="yahoo-connect">
        <AppText style={styles.hint}>{YAHOO_WHY}</AppText>
        {message ? <AppText style={styles.error}>{message}</AppText> : null}
        <PressableScale
          style={[styles.primaryButton, (busy || disabled) && styles.primaryButtonDisabled]}
          disabled={busy || disabled}
          onPress={() => void connect()}
          accessibilityRole="button"
          accessibilityLabel={YAHOO_CONNECT_LABEL}
        >
          <AppText style={styles.primaryText}>{YAHOO_CONNECT_LABEL}</AppText>
        </PressableScale>
      </View>
    );
  }
  return (
    <View testID="yahoo-leagues">
      <AppText style={styles.kicker}>{YAHOO_PICK_HEADING}</AppText>
      {message ? <AppText style={styles.error}>{message}</AppText> : null}
      {leagues.length === 0 && !message ? <AppText style={styles.hint}>{YAHOO_NO_LEAGUES}</AppText> : null}
      {leagues.map((league) => (
        <PressableScale
          key={league.league_key}
          style={styles.leagueRow}
          disabled={disabled}
          onPress={() => onPick(league)}
          accessibilityRole="button"
          accessibilityLabel={league.name}
        >
          <AppText style={styles.leagueName}>{league.name}</AppText>
          <AppText style={styles.meta}>{`${league.season} season · ${league.team_count} teams`}</AppText>
        </PressableScale>
      ))}
      <PressableScale onPress={() => void disconnect()} disabled={busy} accessibilityRole="button" accessibilityLabel="Disconnect Yahoo">
        <AppText style={styles.linkText}>Disconnect Yahoo</AppText>
      </PressableScale>
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    hint: { fontSize: 13.5, color: colors.textSecondary, marginBottom: spacing.md, lineHeight: 18 },
    kicker: { ...typography.kicker, color: colors.textTertiary, textTransform: 'uppercase', marginBottom: spacing.xs },
    error: { fontSize: 13.5, color: colors.danger, marginBottom: spacing.sm, lineHeight: 18 },
    leagueRow: {
      paddingVertical: spacing.sm,
      borderBottomWidth: StyleSheet.hairlineWidth,
      borderBottomColor: colors.border,
    },
    leagueName: { fontSize: 16.5, fontWeight: '600', color: colors.textPrimary },
    meta: { fontSize: 13.5, color: colors.textSecondary, marginTop: 2 },
    linkText: { fontSize: 13.5, fontWeight: '700', color: colors.textTertiary, marginTop: spacing.md },
    primaryButton: {
      backgroundColor: colors.accent,
      paddingHorizontal: spacing.lg,
      paddingVertical: 12,
      borderRadius: radii.sm,
      alignItems: 'center',
    },
    primaryButtonDisabled: { opacity: 0.5 },
    primaryText: { fontSize: 15.5, fontWeight: '700', color: colors.onAccent },
  });
}
