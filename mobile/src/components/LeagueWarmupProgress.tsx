import React, { useEffect, useMemo, useRef, useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import AppText from './AppText';
import { api } from '../lib/api';
import { followLeagueWarmup, WARMUP_STEPS, type WarmupStatus } from '../lib/leagueWarmup';
import { useThemeMode } from '../context/ThemeModeContext';
import { spacing, type ThemeColors } from '../theme';

/**
 * Real first-load progress for a just-saved league: each step is ticked only
 * when the server reports that stage done (GET .../warmup-status). A warm
 * league, a failure or a long wait all call onDone so the caller carries on
 * to the Dashboard; nothing here is timer-driven.
 */
export default function LeagueWarmupProgress({
  leagueId,
  onDone,
}: {
  leagueId: string;
  onDone: () => void;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [status, setStatus] = useState<WarmupStatus | null>(null);
  const doneRef = useRef(onDone);
  doneRef.current = onDone;

  useEffect(
    () =>
      followLeagueWarmup(() => api.getLeagueWarmupStatus(leagueId), {
        onUpdate: setStatus,
        onDone: () => doneRef.current(),
      }),
    [leagueId],
  );

  return (
    <View style={styles.wrap} accessibilityLiveRegion="polite">
      <AppText style={styles.title}>Setting up your league</AppText>
      {WARMUP_STEPS.map((step) => {
        const done = Boolean(status?.stages[step.key]);
        return (
          <View key={step.key} style={styles.row}>
            <Ionicons
              name={done ? 'checkmark-circle' : 'ellipse-outline'}
              size={18}
              color={done ? colors.success : colors.textTertiary}
            />
            <AppText style={[styles.label, done && styles.labelDone]}>{step.label}</AppText>
          </View>
        );
      })}
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    wrap: { gap: spacing.sm, paddingVertical: spacing.md },
    title: { fontSize: 16, fontWeight: '700', color: colors.textPrimary, marginBottom: 4 },
    row: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
    label: { fontSize: 14, color: colors.textSecondary },
    labelDone: { color: colors.textPrimary },
  });
}
