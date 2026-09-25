import React, { useMemo } from 'react';
import { StyleSheet, View } from 'react-native';

import AppText from './AppText';
import { useThemeMode } from '../context/ThemeModeContext';
import { radii, spacing, type ThemeColors } from '../theme';

/**
 * Compact "NEW" pill for an unseen recommendation/insight — originally
 * Dashboard-only (paired with lib/sinceLastCheckIn's new-item diff),
 * promoted into a shared component so any feed of dismissible/refreshing
 * items (Dashboard's briefing cards, the new InsightRow rows) renders the
 * exact same "this is new since your last visit" affordance instead of a
 * page-specific copy.
 */
export default function NewBadge() {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <View style={styles.badge}>
      <AppText style={styles.text}>NEW</AppText>
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    badge: {
      backgroundColor: colors.accent,
      borderRadius: radii.pill,
      paddingHorizontal: spacing.xs + 2,
      paddingVertical: 2,
      marginLeft: spacing.xs,
    },
    text: { fontSize: 8, fontWeight: '800', color: colors.background, letterSpacing: 0.4 },
  });
}
