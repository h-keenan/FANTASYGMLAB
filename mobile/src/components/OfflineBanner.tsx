import React, { useEffect, useMemo, useRef, useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import AppText from './AppText';
import { useThemeMode } from '../context/ThemeModeContext';
import { BACK_ONLINE_TEXT, OFFLINE_BANNER_TEXT } from '../lib/badDayCopy';
import { isOffline, setOffline, subscribeConnectivity } from '../lib/connectivity';
import { env } from '../lib/env';
import { spacing, type ThemeColors } from '../theme';

const RECOVERY_POLL_MS = 10_000;

/**
 * The one offline banner (app). Shown while api.ts reports that requests cannot reach the server (lib/connectivity.ts;
 * NetInfo is not installed), and while shown it polls GET /health so it clears itself on recovery. Cached content stays
 * usable underneath. Mounted once in App.tsx. Web twin: web-next/src/components/OfflineBanner.tsx.
 */
export default function OfflineBanner() {
  const { colors } = useThemeMode();
  const insets = useSafeAreaInsets();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [offline, setOfflineState] = useState(isOffline());
  const [recovered, setRecovered] = useState(false);
  const wasOffline = useRef(offline);

  useEffect(
    () =>
      subscribeConnectivity((next) => {
        setOfflineState(next);
        if (wasOffline.current && !next) {
          setRecovered(true);
          setTimeout(() => setRecovered(false), 3000);
        }
        wasOffline.current = next;
      }),
    [],
  );

  useEffect(() => {
    if (!offline) return undefined;
    const timer = setInterval(() => {
      fetch(`${env.apiBaseUrl}/health`, { method: 'GET' })
        .then(() => setOffline(false))
        .catch(() => undefined);
    }, RECOVERY_POLL_MS);
    return () => clearInterval(timer);
  }, [offline]);

  if (!offline && !recovered) return null;
  return (
    <View
      style={[styles.bar, offline ? styles.offline : styles.online, { paddingTop: Math.max(insets.top, spacing.xs) }]}
      accessibilityRole="alert"
      accessibilityLiveRegion="polite"
      testID="offline-banner"
    >
      <AppText style={styles.text}>{offline ? OFFLINE_BANNER_TEXT : BACK_ONLINE_TEXT}</AppText>
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    bar: { position: 'absolute', top: 0, left: 0, right: 0, zIndex: 999, paddingBottom: spacing.xs, paddingHorizontal: spacing.lg, borderBottomWidth: 1 },
    offline: { backgroundColor: colors.surface, borderBottomColor: colors.warning },
    online: { backgroundColor: colors.surface, borderBottomColor: colors.success },
    text: { fontSize: 12.5, fontWeight: '700', color: colors.textPrimary, textAlign: 'center' },
  });
}
