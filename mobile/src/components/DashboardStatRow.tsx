import React, { useMemo } from 'react';
import { StyleSheet, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import MetricCard from './MetricCard';
import { spacing } from '../theme';

type IconName = React.ComponentProps<typeof Ionicons>['name'];

export type StatStripItem = {
  label: string;
  icon: IconName;
  value: string;
  valueColor?: string;
  onPress?: () => void;
};

/**
 * One row of equal-width stat tiles that never wraps (web: components/StatStrip). The
 * Dashboard's Record / Power Rank / Franchise Rank / Avg Age strip and its
 * Team Snapshot row both render through it.
 */
export default function DashboardStatRow({ items }: { items: StatStripItem[] }) {
  const styles = useMemo(() => createStyles(), []);
  return (
    <View style={styles.row}>
      {items.map((item) => (
        <MetricCard
          key={item.label}
          label={item.label}
          icon={item.icon}
          value={item.value}
          valueColor={item.valueColor}
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
