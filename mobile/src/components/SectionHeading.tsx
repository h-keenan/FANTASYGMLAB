import React, { useMemo } from 'react';
import { StyleSheet, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import AppText from './AppText';
import { useThemeMode } from '../context/ThemeModeContext';
import { spacing, type ThemeColors } from '../theme';

type IconName = React.ComponentProps<typeof Ionicons>['name'];

/**
 * Small accent-icon + Title Case label row that introduces a group of cards
 * (Player Detail's "Bio"/"Model Breakdown"/"Points By Week"/schedule-week
 * headings; Dashboard's "League Snapshot"). Promoted out of
 * PlayerDetailScreen's own private SectionHeading so both screens render the
 * exact same section-heading treatment instead of two near-identical copies
 * (Dashboard previously had its own uppercase/smaller variant) — per the
 * app-wide UI consistency rule, "section headings" are one of the shared
 * patterns every screen should agree on.
 */
export default function SectionHeading({ title, icon }: { title: string; icon: IconName }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <View style={styles.row}>
      <Ionicons name={icon} size={15} color={colors.accent} style={styles.icon} />
      <AppText style={styles.title}>{title}</AppText>
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    row: { flexDirection: 'row', alignItems: 'center', marginBottom: spacing.sm },
    icon: { marginRight: spacing.xs },
    title: { fontSize: 15, fontWeight: '700', color: colors.textPrimary },
  });
}
