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
 * Shared single-row shortcut-tile grid — originally Dashboard's own
 * "Quick Actions" row (PR #683, Trade Hub/Rankings/Waivers/Draft Picks),
 * promoted into a shared component so any hub-style screen (Dashboard,
 * League Detail) renders the exact same tile affordance instead of a
 * page-specific reimplementation. Built on AnimatedCard so every tile gets
 * the same press-scale + resting shadow every other card in the app has.
 * Callers own their own action list/colors/destinations; this only renders.
 *
 * Tile count: both current callers always pass exactly 4 actions, so the
 * default lays out one compact row of 4 rather than wrapping to 2x2. This
 * intentionally keeps the *smaller* icon size and tighter padding coridian_
 * asked for after flagging an earlier 4-per-row/44pt-icon version as "way
 * too big" (screenshot, 2026-09-23) — narrowing the tiles to fit 4 across
 * makes them read as compact/scannable rather than large, so it satisfies
 * that complaint at least as well as the 2-per-row layout did, while also
 * matching the concept sheet's single-row Quick Actions treatment.
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
    // 4-per-row, sized to stay compact rather than large — the whole card
    // is still a comfortable tap target, just narrow. See the component
    // doc comment for why this is 4-across instead of 2x2.
    cell: {
      flexBasis: '22%',
      flexGrow: 1,
      alignItems: 'center',
      paddingVertical: spacing.sm,
      paddingHorizontal: spacing.xs,
      gap: 4,
      borderWidth: 1,
    },
    label: { fontSize: 11, fontWeight: '700', color: colors.textPrimary, textAlign: 'center' },
  });
}
