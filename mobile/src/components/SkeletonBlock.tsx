import React, { useEffect, useMemo } from 'react';
import { StyleSheet, View, type DimensionValue, type StyleProp, type ViewStyle } from 'react-native';
import Animated, {
  Easing,
  useAnimatedStyle,
  useSharedValue,
  withRepeat,
  withTiming,
} from 'react-native-reanimated';

import { radii, spacing, type ThemeColors } from '../theme';
import { useThemeMode } from '../context/ThemeModeContext';

/**
 * Shaped loading placeholder — the "here's the shape of what's coming"
 * counterpart to `BrandedSpinner`. `BrandedSpinner` is still correct for a
 * screen's true cold-start "nothing rendered yet" moment; this is for the
 * gap that spinner's own doc comment doesn't cover — a *secondary* content
 * section (a stats card, a chart, a list row) still loading after primary
 * content already rendered, which used to leave a bare `<ActivityIndicator>`
 * floating alone in a large empty area (e.g. Player Detail's Stats tab
 * while its primary data fetch is in flight — see PlayerDetailScreen.tsx).
 *
 * Reuses `BrandedSpinner`'s exact pulse technique (reanimated's
 * `withRepeat`/`withTiming`, same easing) rather than inventing a new
 * shimmer/animation approach — only the animated property differs
 * (background-color-adjacent opacity pulse over a static neutral fill,
 * instead of pulsing a fixed image's opacity/scale).
 */
export default function SkeletonBlock({
  width = '100%',
  height = 16,
  radius = radii.sm,
  style,
}: {
  width?: DimensionValue;
  height?: number;
  radius?: number;
  style?: StyleProp<ViewStyle>;
}) {
  const { colors } = useThemeMode();
  const pulse = useSharedValue(0);

  useEffect(() => {
    pulse.value = withRepeat(withTiming(1, { duration: 900, easing: Easing.inOut(Easing.ease) }), -1, true);
  }, [pulse]);

  const animatedStyle = useAnimatedStyle(() => ({
    opacity: 0.5 + pulse.value * 0.3,
  }));

  return (
    <Animated.View
      style={[
        {
          width,
          height,
          borderRadius: radius,
          backgroundColor: colors.backgroundElevated,
        },
        animatedStyle,
        style,
      ]}
    />
  );
}

/**
 * Card-shaped placeholder matching `AnalyticsSection`'s own card chrome
 * (surface fill, cardBorder hairline, `radii.md`, header row) so a loading
 * analytics group reads as "a card like this is coming" rather than a void.
 * `rows` controls how many metric-tile-shaped blocks render inside — pass
 * an even number to roughly match a 2-column `MetricCard` grid.
 */
export function SkeletonCard({
  rows = 4,
  style,
}: {
  /** Number of metric-tile-shaped blocks inside the card (MetricCard's grid
   * is 2-up, so pairs look most like the real thing). */
  rows?: number;
  style?: StyleProp<ViewStyle>;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <View style={[styles.card, style]}>
      <View style={styles.cardHeaderRow}>
        <SkeletonBlock width={16} height={16} radius={radii.sm} />
        <SkeletonBlock width={100} height={13} style={styles.cardHeaderTitle} />
      </View>
      <View style={styles.cardGrid}>
        {Array.from({ length: rows }, (_, index) => (
          <SkeletonBlock key={index} width="46%" height={62} radius={radii.sm} style={styles.cardTile} />
        ))}
      </View>
    </View>
  );
}

/** Row-shaped placeholder for a single list item — a player row, a trade
 * card, a waiver recommendation — sized for a portrait/avatar-left,
 * two-line-text-right layout, the shape nearly every list row in the app
 * shares. Colorless by design (its children, `SkeletonBlock`s, carry the
 * only themed fill) so it needs no theme lookup of its own. */
export function SkeletonRow({ style }: { style?: StyleProp<ViewStyle> }) {
  return (
    <View style={[rowStyles.row, style]}>
      <SkeletonBlock width={40} height={40} radius={radii.pill} />
      <View style={rowStyles.rowTextGroup}>
        <SkeletonBlock width="70%" height={14} />
        <SkeletonBlock width="45%" height={11} />
      </View>
    </View>
  );
}

const rowStyles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: spacing.md, paddingVertical: spacing.sm },
  rowTextGroup: { flex: 1, gap: spacing.xs },
});

/** Chart-shaped placeholder sized to `WeeklyPointsChart`'s own fixed
 * `HEIGHT` (140) so the points-by-week section doesn't jump when the real
 * chart mounts — a flat shimmering plot area reads closer to "a chart is
 * loading here" than a spinner centered in the same space. */
export function SkeletonChart({ style }: { style?: StyleProp<ViewStyle> }) {
  return <SkeletonBlock height={140} radius={radii.sm} style={style} />;
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
    cardHeaderRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs, marginBottom: spacing.sm },
    cardHeaderTitle: {},
    cardGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
    cardTile: { minWidth: 64, flexGrow: 1 },
  });
}
