import React, { useMemo } from 'react';
import { StyleProp, StyleSheet, View, ViewStyle } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import MetricCard from './MetricCard';
import { useThemeMode } from '../context/ThemeModeContext';
import { spacing } from '../theme';

type IconName = React.ComponentProps<typeof Ionicons>['name'];

export type StatStripItem = {
  label: string;
  icon?: IconName;
  value: string;
  valueColor?: string;
  /** Semantic value color shortcut; `valueColor` wins when both are set. */
  tone?: 'positive' | 'risk';
  onPress?: () => void;
};

/**
 * One row of equal-width stat tiles that never wraps (web: components/StatStrip). The
 * Dashboard's Record / Power Rank / Franchise Rank / Avg Age strip and its
 * Team Snapshot row both render through it.
 */
export default function DashboardStatRow({ items, style }: { items: StatStripItem[]; style?: StyleProp<ViewStyle> }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(), []);
  return (
    <View style={[styles.row, style]} accessibilityLabel="Summary">
      {items.map((item) => (
        <MetricCard
          key={item.label}
          label={item.label}
          icon={item.icon}
          value={item.value}
          valueColor={
            item.valueColor ?? (item.tone === 'positive' ? colors.successBright : item.tone === 'risk' ? colors.danger : undefined)
          }
          onPress={item.onPress}
          style={styles.tile}
        />
      ))}
    </View>
  );
}

function createStyles() {
  return StyleSheet.create({
    row: { flexDirection: 'row', gap: spacing.sm, marginBottom: spacing.md },
    tile: { flexBasis: 0, flexGrow: 1, minWidth: 0, paddingHorizontal: spacing.sm },
  });
}
