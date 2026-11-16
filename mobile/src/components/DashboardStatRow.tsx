import React, { useMemo } from 'react';
import { StyleProp, StyleSheet, View, ViewStyle } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import MetricCard from './MetricCard';
import InfoMark, { type InfoMarkProps } from './InfoMark';
import type { WhyMetricId } from '../lib/tapForWhyContent.ts';
import { useThemeMode } from '../context/ThemeModeContext';
import { spacing, type ThemeColors } from '../theme';

type IconName = React.ComponentProps<typeof Ionicons>['name'];

export type StatStripItem = {
  label: string;
  icon?: IconName;
  value: string;
  /** Dollar amount that counts up/down (see MetricCard `amount`); `value` remains the text fallback. */
  amount?: number | null;
  valueColor?: string;
  /** Semantic value color shortcut; `valueColor` wins when both are set. */
  tone?: 'positive' | 'risk';
  /** 0..1 standing drawn as a thin meter under the value (see MetricCard `fill`). */
  fill?: number | null;
  /** Short context under the value ("of 12 teams", "League avg 26.1"). */
  note?: string | null;
  onPress?: () => void;
  /** A metric this strip's one InfoMark explains (lib/tapForWhyContent.ts). All of a strip's `why` metrics merge into ONE "?" after the first tagged label; modules with a title (StatStripModule) put it on the title instead. */
  why?: WhyMetricId;
};

/**
 * One row of equal-width stat tiles that never wraps (web: components/StatStrip). The
 * Dashboard's Record / Power Rank / Franchise Rank / Avg Age strip and its
 * Team Snapshot row both render through it.
 */
export default function DashboardStatRow({ items, style, info }: { items: StatStripItem[]; style?: StyleProp<ViewStyle>; info?: Omit<InfoMarkProps, 'label' | 'metrics'> }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const whyMetrics = items.map((i) => i.why).filter((w): w is WhyMetricId => Boolean(w));
  const infoIndex = items.findIndex((i) => i.why) >= 0 ? items.findIndex((i) => i.why) : info ? 0 : -1;
  return (
    <View style={[styles.row, style]} accessibilityLabel="Summary">
      {items.map((item, index) => (
        <View key={item.label} style={styles.cell}>
        <MetricCard
          label={item.label}
          icon={item.icon}
          value={item.value}
          amount={item.amount}
          valueColor={
            item.valueColor ?? (item.tone === 'positive' ? colors.successBright : item.tone === 'risk' ? colors.danger : undefined)
          }
          fill={item.fill}
          note={item.note}
          onPress={item.onPress}
          centered
          style={styles.tile}
          labelAccessory={index === infoIndex ? <InfoMark label="this summary" metrics={whyMetrics} testID={whyMetrics[0] ? `why-${whyMetrics[0]}` : undefined} {...info} /> : undefined}
        />
        </View>
      ))}
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    row: { flexDirection: 'row', gap: spacing.sm, marginBottom: spacing.md },
    cell: { flexBasis: 0, flexGrow: 1, minWidth: 0 },
    tile: { alignSelf: 'stretch', minWidth: 0, paddingHorizontal: spacing.sm },
  });
}
