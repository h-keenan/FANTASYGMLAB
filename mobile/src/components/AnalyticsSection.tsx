import React, { useMemo } from 'react';
import { StyleSheet, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import AppText from './AppText';
import { useThemeMode } from '../context/ThemeModeContext';
import { radii, spacing, type ThemeColors } from '../theme';

type IoniconName = React.ComponentProps<typeof Ionicons>['name'];

/**
 * One analytic-group card for the Stats tab — "Fantasy Scoring", "Production",
 * "Receiving", "Usage", "Efficiency" each get their own compact bordered
 * card with an icon+title header, per the concept sheet (previously these
 * were folded into one long card with hairline dividers between them).
 * Content-agnostic: takes children so it can host either a MetricCard grid
 * or the Usage section's percent-bar rows without duplicating either.
 */
export default function AnalyticsSection({
  title,
  icon,
  children,
  footer,
}: {
  title: string;
  icon: IoniconName;
  children: React.ReactNode;
  /** Optional trailing control on the header row, e.g. a season picker. */
  footer?: React.ReactNode;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <View style={styles.card}>
      <View style={styles.headerRow}>
        <View style={styles.headerTitleRow}>
          <Ionicons name={icon} size={14} color={colors.accent} style={styles.headerIcon} />
          <AppText style={styles.title}>{title}</AppText>
        </View>
        {footer ?? null}
      </View>
      <View>{children}</View>
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    card: {
      backgroundColor: colors.surface,
      borderRadius: radii.md,
      borderWidth: StyleSheet.hairlineWidth * 1.5,
      borderColor: colors.cardBorder,
      padding: spacing.md,
      marginTop: spacing.sm,
    },
    headerRow: {
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent: 'space-between',
      marginBottom: spacing.sm,
    },
    headerTitleRow: { flexDirection: 'row', alignItems: 'center' },
    headerIcon: { marginRight: spacing.xs },
    title: { fontSize: 13, fontWeight: '700', color: colors.textPrimary },
  });
}
