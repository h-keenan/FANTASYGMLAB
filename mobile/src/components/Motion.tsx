import React, { useEffect, useRef, useState, type ReactNode } from 'react';
import { Animated, Easing, StyleSheet, View, type StyleProp, type ViewStyle } from 'react-native';

import { useThemeMode } from '../context/ThemeModeContext';
import { COUNT_MS, EASE, MOTION_MS, confettiAllowed, confettiPieces, countUpValue, shouldAnimateList, staggerDelay } from '../lib/motion';
import { useReducedMotion } from '../lib/useMotion';

const easeOut = Easing.bezier(...EASE.out);

/**
 * Entrance for one block (twin of web-next/src/components/Motion.tsx MotionIn): fades and rises a few px on mount
 * (transform/opacity only, native driver). `index` / `count` stagger a group with a capped total; lists over
 * MAX_ANIMATED_ROWS and reduced motion do not animate at all. Never changes layout.
 */
export function MotionIn({ children, index = 0, count = 1, style }: { children: ReactNode; index?: number; count?: number; style?: StyleProp<ViewStyle> }) {
  const reduced = useReducedMotion();
  const animate = !reduced && shouldAnimateList(count);
  const progress = useRef(new Animated.Value(animate ? 0 : 1)).current;
  useEffect(() => {
    if (!animate) {
      progress.setValue(1);
      return;
    }
    Animated.timing(progress, { toValue: 1, duration: MOTION_MS.base, delay: staggerDelay(index, count), easing: easeOut, useNativeDriver: true }).start();
  }, [animate, index, count, progress]);
  return (
    <Animated.View style={[style, { opacity: progress, transform: [{ translateY: progress.interpolate({ inputRange: [0, 1], outputRange: [8, 0] }) }] }]}>
      {children}
    </Animated.View>
  );
}

/** A number that counts up from 0 the first time it appears, then follows changes without recounting. Reduced motion: the final value. */
export function CountUp({ value, decimals = 1, render }: { value: number; decimals?: number; render: (text: string) => ReactNode }) {
  const reduced = useReducedMotion();
  const [shown, setShown] = useState(value);
  const first = useRef(true);
  useEffect(() => {
    if (reduced || !first.current) {
      setShown(value);
      return;
    }
    first.current = false;
    const start = Date.now();
    let raf = 0;
    setShown(0);
    const step = () => {
      const t = (Date.now() - start) / COUNT_MS;
      setShown(countUpValue(0, value, t));
      if (t < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [value, reduced]);
  return <>{render(shown.toFixed(decimals))}</>;
}

/** Confetti burst for a title only; nothing otherwise or under reduced motion. Transform/opacity pieces on the native driver. */
export function Confetti({ wonTitle }: { wonTitle: boolean }) {
  const reduced = useReducedMotion();
  const { colors } = useThemeMode();
  const t = useRef(new Animated.Value(0)).current;
  const on = confettiAllowed({ wonTitle, reduced });
  useEffect(() => {
    if (!on) return;
    Animated.timing(t, { toValue: 1, duration: 1200, easing: easeOut, useNativeDriver: true }).start();
  }, [on, t]);
  if (!on) return null;
  const palette = [colors.accent, colors.success, colors.warning, colors.textPrimary];
  return (
    <View pointerEvents="none" style={styles.confetti} accessibilityElementsHidden importantForAccessibility="no-hide-descendants" testID="confetti">
      {confettiPieces().map((p, i) => (
        <Animated.View
          key={i}
          style={[
            styles.piece,
            {
              backgroundColor: palette[p.hue],
              opacity: t.interpolate({ inputRange: [0, 0.8, 1], outputRange: [1, 1, 0] }),
              transform: [
                { translateX: t.interpolate({ inputRange: [0, 1], outputRange: [0, p.x] }) },
                { translateY: t.interpolate({ inputRange: [0, 1], outputRange: [0, p.y + 80] }) },
                { rotate: t.interpolate({ inputRange: [0, 1], outputRange: ['0deg', `${p.rotate}deg`] }) },
              ],
            },
          ]}
        />
      ))}
    </View>
  );
}

/** Wraps a badge/count: pulses once whenever the count goes up (new item), never on first render. */
export function PulseOnIncrease({ value, children }: { value: number; children: ReactNode }) {
  const reduced = useReducedMotion();
  const scale = useRef(new Animated.Value(1)).current;
  const previous = useRef(value);
  useEffect(() => {
    if (value > previous.current && !reduced) {
      Animated.sequence([
        Animated.timing(scale, { toValue: 1.25, duration: MOTION_MS.instant, easing: easeOut, useNativeDriver: true }),
        Animated.timing(scale, { toValue: 1, duration: MOTION_MS.base, easing: easeOut, useNativeDriver: true }),
      ]).start();
    }
    previous.current = value;
  }, [value, reduced, scale]);
  return <Animated.View style={{ transform: [{ scale }] }}>{children}</Animated.View>;
}

const styles = StyleSheet.create({
  confetti: { position: 'absolute', left: '50%', top: '30%', width: 0, height: 0, zIndex: 95 },
  piece: { position: 'absolute', width: 8, height: 12, borderRadius: 2 },
});
