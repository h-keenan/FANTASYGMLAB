import React, { useEffect } from 'react';
import { StyleSheet, View } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import Animated, {
  Easing,
  useAnimatedStyle,
  useReducedMotion,
  useSharedValue,
  withRepeat,
  withTiming,
} from 'react-native-reanimated';

/**
 * "Signal" onboarding backdrop: a slow cyan -> violet aurora (theme.accent
 * and theme.violet, the same hues as web's .onboarding-aurora). Purely
 * decorative and non-interactive; it sits behind the slides and holds still
 * under reduced motion. Twin of web-next's `.onboarding-aurora`.
 */
export default function OnboardingAurora({ cyan, violet }: { cyan: string; violet: string }) {
  const reduceMotion = useReducedMotion();
  const t = useSharedValue(0);
  useEffect(() => {
    if (reduceMotion) {
      t.value = 0;
      return;
    }
    t.value = withRepeat(withTiming(1, { duration: 9000, easing: Easing.inOut(Easing.ease) }), -1, true);
  }, [reduceMotion, t]);
  const driftA = useAnimatedStyle(() => ({
    transform: [{ translateX: -14 + t.value * 28 }, { translateY: -6 + t.value * 18 }, { scale: 1 + t.value * 0.08 }],
  }));
  const driftB = useAnimatedStyle(() => ({
    transform: [{ translateX: 14 - t.value * 28 }, { translateY: 8 - t.value * 18 }, { scale: 1.08 - t.value * 0.08 }],
  }));
  return (
    <View pointerEvents="none" style={StyleSheet.absoluteFill} accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
      <Animated.View style={[styles.blob, styles.blobA, driftA]}>
        <LinearGradient colors={[`${cyan}59`, `${cyan}00`]} style={styles.fill} start={{ x: 0.3, y: 0.2 }} end={{ x: 0.7, y: 1 }} />
      </Animated.View>
      <Animated.View style={[styles.blob, styles.blobB, driftB]}>
        <LinearGradient colors={[`${violet}66`, `${violet}00`]} style={styles.fill} start={{ x: 0.7, y: 0.1 }} end={{ x: 0.3, y: 1 }} />
      </Animated.View>
    </View>
  );
}

const styles = StyleSheet.create({
  blob: { position: 'absolute', width: 360, height: 360, borderRadius: 180, overflow: 'hidden' },
  blobA: { top: -110, left: -90 },
  blobB: { top: -60, right: -120 },
  fill: { flex: 1 },
});
