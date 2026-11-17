import React, { useMemo } from 'react';
import { StyleSheet, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import AppText from './AppText';
import PressableScale from './PressableScale';
import { useThemeMode } from '../context/ThemeModeContext';
import { spacing, type ThemeColors } from '../theme';

/**
 * THE one compact page sub-line (UI audit batch B, docs/audits/2026-11-ui-audit-e2e.md P0-2): context on the left ("Week 10", a Live
 * badge), freshness + a refresh icon on the right, one row about 32pt tall, with the standard small gap to the first module (the
 * parent's gap, `pageTopGap`). It replaces the separate title/week row and the separate "Updated 3m ago . Refresh" row; the page must
 * not repeat what it says (the week) inside the first card. The 44pt refresh target is kept with hitSlop, so the row stays compact.
 * Web twin: web-next/src/components/ui/PageStatusLine.tsx.
 */
export default function PageStatusLine({
  context,
  freshness,
  onRefresh,
  refreshing = false,
  refreshLabel = 'Refresh',
  testID = 'page-status-line',
}: {
  context?: React.ReactNode;
  /** "Updated 3m ago"; omit when there is nothing to show. */
  freshness?: string | null;
  onRefresh?: () => void;
  refreshing?: boolean;
  refreshLabel?: string;
  testID?: string;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  if (!context && !freshness && !onRefresh) return null;
  return (
    <View style={styles.row} testID={testID}>
      <View style={styles.context}>{context}</View>
      <View style={styles.right}>
        {freshness ? (
          <AppText style={styles.freshness} accessibilityLiveRegion="polite">
            {freshness}
          </AppText>
        ) : null}
        {onRefresh ? (
          <PressableScale
            onPress={onRefresh}
            disabled={refreshing}
            accessibilityRole="button"
            accessibilityLabel={refreshing ? 'Refreshing' : refreshLabel}
            hitSlop={{ top: 6, bottom: 6, left: 8, right: 8 }}
            style={styles.refresh}
            testID={`${testID}-refresh`}
          >
            <Ionicons name="refresh" size={18} color={colors.accent} style={refreshing ? styles.refreshing : undefined} />
          </PressableScale>
        ) : null}
      </View>
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    row: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', minHeight: 32, gap: spacing.sm },
    context: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, flexShrink: 1 },
    right: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
    freshness: { fontSize: 12.5, color: colors.textSecondary },
    refresh: { width: 32, height: 32, alignItems: 'center', justifyContent: 'center' },
    refreshing: { opacity: 0.5 },
  });
}
