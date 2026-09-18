import React, { useEffect } from 'react';
import { Image, StyleSheet, Text, View } from 'react-native';
import Animated, {
  Easing,
  useAnimatedStyle,
  useSharedValue,
  withRepeat,
  withTiming,
} from 'react-native-reanimated';

import { colors, radii, spacing } from '../theme';

/**
 * Branded launch/loading state, matching the web app's splash (FGL mark,
 * "FOUNDER BETA" badge, a short status line) rather than a bare spinner.
 *
 * The mark pulses gently — this screen can sit on cold start for a couple
 * of real seconds waiting on the auth check, and a fully static screen in
 * that window reads as frozen/broken rather than working.
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
      <Animated.Image source={require('../../assets/icon.png')} style={[styles.mark, markStyle]} />
      <Text style={styles.title}>FantasyGM Lab</Text>
      <View style={styles.badge}>
        <Text style={styles.badgeText}>FOUNDER BETA</Text>
      </View>
      <Text style={styles.status}>{status}</Text>
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
  mark: { width: 72, height: 72, borderRadius: radii.md, marginBottom: spacing.md },
  title: { fontSize: 22, fontWeight: '700', color: colors.textPrimary },
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
