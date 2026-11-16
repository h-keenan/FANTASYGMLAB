import React, { useMemo } from 'react';
import { StyleProp, StyleSheet, View, ViewStyle } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import MetricCard from './MetricCard';
import TapForWhy from './TapForWhy';
import type { WhyMetricId } from '../lib/tapForWhyContent.ts';
import { useThemeMode } from '../context/ThemeModeContext';
import AppText from './AppText';
import { spacing, type ThemeColors } from '../theme';

type IconName = React.ComponentProps<typeof Ionicons>['name'];

export type StatStripItem = {
  label: string;
  icon?: IconName;
  value: string;
  valueColor?: string;
  /** Semantic value color shortcut; `valueColor` wins when both are set. */
  tone?: 'positive' | 'risk';
  /** 0..1 standing drawn as a thin meter under the value (see MetricCard `fill`). */
  fill?: number | null;
  /** Short context under the value ("of 12 teams", "League avg 26.1"). */
  note?: string | null;
  onPress?: () => void;
  /** The metric the small 44pt "why" target in the tile corner explains (lib/tapForWhyContent.ts). The tile tap keeps its own action. */
  why?: WhyMetricId;
};

/**
 * One row of equal-width stat tiles that never wraps (web: components/StatStrip). The
 * Dashboard's Record / Power Rank / Franchise Rank / Avg Age strip and its
 * Team Snapshot row both render through it.
 */
export default function DashboardStatRow({ items, style }: { items: StatStripItem[]; style?: StyleProp<ViewStyle> }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <View style={[styles.row, style]} accessibilityLabel="Summary">
      {items.map((item) => (
        <View key={item.label} style={styles.cell}>
        <MetricCard
          label={item.label}
          icon={item.icon}
          value={item.value}
          valueColor={
            item.valueColor ?? (item.tone === 'positive' ? colors.successBright : item.tone === 'risk' ? colors.danger : undefined)
          }
          fill={item.fill}
          note={item.note}
          onPress={item.onPress}
          centered
          style={styles.tile}
        />
        {item.why ? (
          <View style={styles.why} pointerEvents="box-none">
            <TapForWhy metric={item.why} spoken={item.label} variant="chip" style={styles.whyBtn} testID={`why-${item.why}`}>
              <AppText style={styles.whyGlyph}>?</AppText>
            </TapForWhy>
          </View>
        ) : null}
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
    why: { position: 'absolute', top: 0, right: 0, width: 44, height: 44, alignItems: 'flex-end' },
    whyBtn: { width: 22, height: 22, margin: 4, borderRadius: 11, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.glassInset },
    whyGlyph: { fontSize: 12, fontWeight: '800', color: colors.textTertiary },
  });
}
