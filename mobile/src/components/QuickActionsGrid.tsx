import React, { useMemo } from 'react';
import { StyleSheet, View, type StyleProp, type ViewStyle } from 'react-native';

import AnimatedCard from './AnimatedCard';
import AppText from './AppText';
import IconCircle from './IconCircle';
import { useThemeMode } from '../context/ThemeModeContext';
import { spacing, type ThemeColors } from '../theme';

export interface QuickAction {
  /** Stable key for the list — usually the destination route name. */
  key: string;
  label: string;
  icon: React.ComponentProps<typeof IconCircle>['name'];
  /** Fixed app-wide semantic color for this destination (see GmOrb's
   * destination list) — never a one-off hue invented per screen. */
  color: string;
  onPress: () => void;
}

/**
 * Shared 2-column shortcut-tile grid — originally Dashboard's own
 * "Quick Actions" row (PR #683, Trade Hub/Rankings/Waivers/Draft Picks),
 * promoted into a shared component so any hub-style screen (Dashboard,
 * League Detail) renders the exact same tile affordance instead of a
 * page-specific reimplementation. Built on AnimatedCard so every tile gets
 * the same press-scale + resting shadow every other card in the app has.
 * Callers own their own action list/colors/destinations; this only renders.
 */
export default function QuickActionsGrid({
  actions,
  style,
}: {
  actions: QuickAction[];
  /** Optional spacing override for the grid's own container — callers that
   * don't already rely on a `gap` between their screen's top-level sections
   * (e.g. Dashboard's manual-margin layout) pass a marginBottom here instead
   * of the grid inventing its own opinion about screen spacing. */
  style?: StyleProp<ViewStyle>;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <View style={[styles.grid, style]}>
      {actions.map((action) => (
        <AnimatedCard
          key={action.key}
          style={StyleSheet.flatten([styles.cell, { borderColor: `${action.color}55` }])}
          onPress={action.onPress}
        >
          <IconCircle name={action.icon} color={action.color} size={34} />
          <AppText style={styles.label} numberOfLines={1}>
            {action.label}
          </AppText>
        </AnimatedCard>
      ))}
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    grid: {
      flexDirection: 'row',
      flexWrap: 'wrap',
      gap: spacing.sm,
    },
    // 2-per-row — still a comfortable tap target (the whole card is
    // tappable), but compact: coridian_ flagged the original lg-padded,
    // 44pt-icon version as "way too big" for a 4-tile row (screenshot,
    // 2026-09-23).
    cell: {
      flexBasis: '47%',
      flexGrow: 1,
      alignItems: 'center',
      paddingVertical: spacing.sm + 2,
      paddingHorizontal: spacing.sm,
      gap: spacing.xs,
      borderWidth: 1,
    },
    label: { fontSize: 12, fontWeight: '700', color: colors.textPrimary, textAlign: 'center' },
  });
}
