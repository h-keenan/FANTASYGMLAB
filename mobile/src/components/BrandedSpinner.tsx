import React, { useEffect, useMemo } from 'react';
import { Image, StyleSheet, View, type StyleProp, type ViewStyle } from 'react-native';
import AppText from './AppText';
import Animated, {
  Easing,
  useAnimatedStyle,
  useSharedValue,
  withRepeat,
  withTiming,
} from 'react-native-reanimated';

import { useThemeMode } from '../context/ThemeModeContext';
import { radii, spacing, type ThemeColors } from '../theme';

/**
 * Compact branded loading state for a single screen's "still loading initial
 * data" moment — the in-screen sibling of LoadingScreen's cold-start splash.
 * Reuses that screen's pulsing-mark technique (same easing/duration) at a
 * footprint sized for replacing a bare `<ActivityIndicator>`, so a screen
 * that's still fetching its primary data doesn't read as dead/broken.
 *
 * Not for secondary/inline spinners (button save state, share-sheet
 * "capturing", a background refresh over already-rendered content) — those
 * stay as plain `<ActivityIndicator>`.
 */
export default function BrandedSpinner({
  label,
  style,
}: {
  /** Optional short status line under the mark, e.g. "Loading your team…". */
  label?: string;
  style?: StyleProp<ViewStyle>;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const pulse = useSharedValue(0);

  useEffect(() => {
    pulse.value = withRepeat(withTiming(1, { duration: 900, easing: Easing.inOut(Easing.ease) }), -1, true);
  }, [pulse]);

  const markStyle = useAnimatedStyle(() => ({
    opacity: 0.6 + pulse.value * 0.4,
    transform: [{ scale: 0.96 + pulse.value * 0.04 }],
  }));

  return (
    <View style={[styles.container, style]}>
      <Animated.Image source={require('../../assets/icon.png')} style={[styles.mark, markStyle]} />
      {label ? <AppText style={styles.label}>{label}</AppText> : null}
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    container: { alignItems: 'center', justifyContent: 'center', gap: spacing.sm },
    mark: { width: 40, height: 40, borderRadius: radii.md },
    label: { fontSize: 12, fontWeight: '600', color: colors.textSecondary, marginTop: spacing.xs },
  });
}
