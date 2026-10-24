import React, { useMemo } from 'react';
import { StyleSheet, View } from 'react-native';

import AppText from './AppText';
import IconCircle from './IconCircle';
import { useThemeMode } from '../context/ThemeModeContext';
import { radii, spacing, type ThemeColors } from '../theme';

/**
 * Decision Fit as its own card (owner's PQV concept, 2026-10-21): icon disc
 * on the left, an accent "DECISION FIT" label, then the backend's
 * one-sentence narrative. Mobile twin of web-next's DecisionFitCard
 * (PlayerHeroHeader.tsx).
 */
export default function DecisionFitCard({ narrative }: { narrative: string }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <View style={styles.card}>
      <IconCircle name="stats-chart" color={colors.accent} size={38} />
      <View style={styles.copy}>
        <AppText style={styles.label}>DECISION FIT</AppText>
        <AppText style={styles.narrative}>{narrative}</AppText>
      </View>
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    card: {
      flexDirection: 'row',
      alignItems: 'flex-start',
      gap: spacing.md,
      padding: spacing.md,
      marginBottom: spacing.lg,
      borderRadius: radii.md,
      borderWidth: 1,
      borderColor: colors.glassBorder,
      backgroundColor: colors.glass,
    },
    copy: { flex: 1, gap: spacing.xs },
    label: { fontSize: 11, fontWeight: '800', letterSpacing: 1, color: colors.accent },
    narrative: { fontSize: 14, lineHeight: 20, color: colors.textSecondary },
  });
}
