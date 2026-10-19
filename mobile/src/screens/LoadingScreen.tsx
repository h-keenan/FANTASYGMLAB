import React, { useEffect, useMemo } from 'react';
import { StyleSheet, View } from 'react-native';
import AppText from '../components/AppText';
import Animated, {
  Easing,
  useAnimatedStyle,
  useSharedValue,
  withRepeat,
  withTiming,
} from 'react-native-reanimated';

import BrandMark from '../components/BrandMark';
import { useThemeMode } from '../context/ThemeModeContext';
import { spacing, type ThemeColors } from '../theme';

/**
 * Branded launch/loading state, matching the web app's splash (FGL mark,
 * product name, a short status line) rather than a bare spinner.
 *
 * The mark pulses gently — this screen can sit on cold start for a couple
 * of real seconds waiting on the auth check, and a fully static screen in
 * that window reads as frozen/broken rather than working.
 *
 * Uses the shared BrandMark (the theme-tinted FD mark) rather than a boxed app-icon tile, so this screen and the GM orb /
 * dashboard empty state all share the same current brand mark instead of
 * each carrying their own copy that can drift out of date.
 */
export default function LoadingScreen({ status = 'Loading…' }: { status?: string }) {
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
    <View style={styles.container}>
      <Animated.View style={markStyle}>
        <BrandMark width={180} height={122} />
      </Animated.View>
      <AppText style={styles.title}>FantasyDesk</AppText>
      <AppText style={styles.status}>{status}</AppText>
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
  container: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.background,
    gap: spacing.sm,
  },
  title: { fontSize: 22, fontWeight: '700', color: colors.textPrimary, marginTop: spacing.md },
  status: { fontSize: 14, color: colors.textSecondary, marginTop: spacing.lg },
  });
}
