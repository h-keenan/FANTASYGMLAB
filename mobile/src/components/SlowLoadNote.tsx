import React, { useEffect, useMemo, useState } from 'react';
import { StyleSheet, View } from 'react-native';

import AppText from './AppText';
import Button from './Button';
import { useThemeMode } from '../context/ThemeModeContext';
import { SLOW_LOAD_AFTER_MS, SLOW_LOAD_RETRY_AFTER_MS, SLOW_LOAD_RETRY_LABEL, SLOW_LOAD_TEXT } from '../lib/badDayCopy';
import { spacing, type ThemeColors } from '../theme';

/**
 * Inside a page-level skeleton: after SLOW_LOAD_AFTER_MS says the load is slow, after SLOW_LOAD_RETRY_AFTER_MS offers a
 * retry (when the screen supplies one). Requests give up at 30s and the screen then shows the shared ErrorState.
 * Web twin: web-next/src/components/SlowLoadNote.tsx.
 */
export default function SlowLoadNote({ onRetry }: { onRetry?: () => void }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [phase, setPhase] = useState<0 | 1 | 2>(0);
  useEffect(() => {
    const slow = setTimeout(() => setPhase(1), SLOW_LOAD_AFTER_MS);
    const retry = setTimeout(() => setPhase(2), SLOW_LOAD_RETRY_AFTER_MS);
    return () => {
      clearTimeout(slow);
      clearTimeout(retry);
    };
  }, []);
  if (phase === 0) return null;
  return (
    <View style={styles.row} testID="slow-load-note">
      <AppText style={styles.text} accessibilityLiveRegion="polite">
        {SLOW_LOAD_TEXT}
      </AppText>
      {phase === 2 && onRetry ? <Button label={SLOW_LOAD_RETRY_LABEL} onPress={onRetry} size="sm" /> : null}
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    row: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, flexWrap: 'wrap' },
    text: { flex: 1, fontSize: 13, color: colors.textSecondary },
  });
}
