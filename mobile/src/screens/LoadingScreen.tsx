import React, { useEffect } from 'react';
import { StyleSheet, View } from 'react-native';
import AppText from '../components/AppText';
import Animated, {
  Easing,
  useAnimatedStyle,
  useSharedValue,
  withRepeat,
  withTiming,
} from 'react-native-reanimated';

import TrajectoryArcs from '../components/TrajectoryArcs';
import { colors, radii, spacing } from '../theme';

/**
 * Branded launch/loading state, matching the web app's splash (FGL mark,
 * "FOUNDER BETA" badge, a short status line) rather than a bare spinner.
 *
 * The mark pulses gently — this screen can sit on cold start for a couple
 * of real seconds waiting on the auth check, and a fully static screen in
 * that window reads as frozen/broken rather than working.
 *
 * Uses the live TrajectoryArcs mark (not the static icon PNG) — the concept
 * sheet's splash/loading panel shows the arc motif directly rather than a
 * boxed app-icon tile, and this is the first of several surfaces (empty
 * states, success confirmations) meant to share this same drawn mark.
 */
export default function LoadingScreen({ status = 'Loading…' }: { status?: string }) {
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
        <TrajectoryArcs width={180} height={122} />
      </Animated.View>
      <AppText style={styles.title}>FantasyGM Lab</AppText>
      <View style={styles.badge}>
        <AppText style={styles.badgeText}>FOUNDER BETA</AppText>
      </View>
      <AppText style={styles.status}>{status}</AppText>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.background,
    gap: spacing.sm,
  },
  title: { fontSize: 22, fontWeight: '700', color: colors.textPrimary, marginTop: spacing.md },
  badge: {
    borderWidth: 1,
    borderColor: colors.accent,
    borderRadius: radii.sm,
    paddingHorizontal: spacing.sm,
    paddingVertical: 3,
    marginTop: spacing.xs,
  },
  badgeText: { fontSize: 11, fontWeight: '700', color: colors.accent, letterSpacing: 0.6 },
  status: { fontSize: 14, color: colors.textSecondary, marginTop: spacing.lg },
});
