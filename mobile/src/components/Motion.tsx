import React, { useEffect, useRef, useState, type ReactNode } from 'react';
import { Animated, Easing, StyleSheet, View, type StyleProp, type ViewStyle } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { useThemeMode } from '../context/ThemeModeContext';
import { COUNT_MS, EASE, MOTION_MS, PROGRESS_MS, RANK_CHIP_MS, SPRING, confettiAllowed, confettiPieces, countUpValue, flipOffset, progressScale, rankChange, shouldAnimateList, staggerDelay } from '../lib/motion';
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

/**
 * THE progress fill (twin of web ProgressFill): grows to `percent` (0-100) when it appears and follows changes, on the native
 * driver (`scaleX` pinned to the left edge, never `width`). Put it in a fixed-height track with `overflow: 'hidden'` and the
 * radius (every bar here is). Reduced motion: the final width at once.
 */
export function ProgressFill({ percent, color, style }: { percent: number | null | undefined; color: string; style?: StyleProp<ViewStyle> }) {
  const reduced = useReducedMotion();
  const target = progressScale(percent);
  const progress = useRef(new Animated.Value(reduced ? target : 0)).current;
  const [width, setWidth] = useState(0);
  useEffect(() => {
    if (reduced) {
      progress.setValue(target);
      return;
    }
    Animated.timing(progress, { toValue: target, duration: PROGRESS_MS, easing: easeOut, useNativeDriver: true }).start();
  }, [target, reduced, progress]);
  return (
    <View style={[{ width: '100%', height: '100%' }, style]} onLayout={(e) => setWidth(e.nativeEvent.layout.width)} testID="progress-fill">
      <Animated.View
        style={{
          width: '100%',
          height: '100%',
          backgroundColor: color,
          // scaleX grows from the centre; the translate pins the left edge.
          transform: [{ translateX: progress.interpolate({ inputRange: [0, 1], outputRange: [-width / 2, 0] }) }, { scaleX: progress }],
        }}
      />
    </View>
  );
}

/** "Up 2" / "down 1" chip when a rank improves or slips; fades after a couple of seconds, never on first render. */
export function RankChip({ rank }: { rank: number | null | undefined }) {
  const { colors } = useThemeMode();
  const reduced = useReducedMotion();
  const previous = useRef(rank);
  const [chip, setChip] = useState<{ dir: 'up' | 'down'; by: number } | null>(null);
  const appear = useRef(new Animated.Value(reduced ? 1 : 0)).current;
  useEffect(() => {
    const change = rankChange(previous.current, rank);
    previous.current = rank;
    if (!change) return;
    setChip(change);
    appear.setValue(reduced ? 1 : 0);
    if (!reduced) Animated.timing(appear, { toValue: 1, duration: MOTION_MS.base, easing: easeOut, useNativeDriver: true }).start();
    const timer = setTimeout(() => setChip(null), RANK_CHIP_MS);
    return () => clearTimeout(timer);
  }, [rank, reduced, appear]);
  if (!chip) return null;
  const tone = chip.dir === 'up' ? colors.success : colors.danger;
  return (
    <Animated.View
      accessibilityLabel={`${chip.dir === 'up' ? 'Up' : 'Down'} ${chip.by}`}
      style={{ opacity: appear, transform: [{ translateY: appear.interpolate({ inputRange: [0, 1], outputRange: [4, 0] }) }], paddingHorizontal: 5, paddingVertical: 2, borderRadius: 999, backgroundColor: colors.backgroundElevated }}
    >
      <Animated.Text style={{ color: tone, fontSize: 12, fontWeight: '800' }}>{chip.dir === 'up' ? '▲' : '▼'}{chip.by}</Animated.Text>
    </Animated.View>
  );
}

/** The success confirmation (a claim landed, a trade was accepted): a check that pops in with a soft spring. Static under reduced motion. */
export function SuccessCheck({ size = 28, label = 'Done' }: { size?: number; label?: string }) {
  const { colors } = useThemeMode();
  const reduced = useReducedMotion();
  const scale = useRef(new Animated.Value(reduced ? 1 : 0.4)).current;
  useEffect(() => {
    if (reduced) return;
    Animated.spring(scale, { toValue: 1, ...SPRING.settle, useNativeDriver: true }).start();
  }, [reduced, scale]);
  return (
    <Animated.View accessibilityRole="image" accessibilityLabel={label} style={{ opacity: scale.interpolate({ inputRange: [0.4, 1], outputRange: [0, 1], extrapolate: 'clamp' }), transform: [{ scale }] }}>
      <Ionicons name="checkmark-circle" size={size} color={colors.success} />
    </Animated.View>
  );
}

/**
 * FLIP reorder for one row of a list that changes order (twin of web useFlipList): when the row's y changes it starts at the
 * old offset and glides to 0 (transform only, native driver, 240ms). No animation under reduced motion, for the first layout,
 * or past MAX_ANIMATED_ROWS rows (pass `animate={false}`).
 */
export function ReorderRow({ children, animate = true, style }: { children: ReactNode; animate?: boolean; style?: StyleProp<ViewStyle> }) {
  const reduced = useReducedMotion();
  const offset = useRef(new Animated.Value(0)).current;
  const lastY = useRef<number | null>(null);
  return (
    <Animated.View
      style={[style, { transform: [{ translateY: offset }] }]}
      onLayout={(e) => {
        const y = e.nativeEvent.layout.y;
        const prev = lastY.current;
        lastY.current = y;
        if (prev == null || reduced || !animate) return;
        const move = flipOffset({ x: 0, y: prev }, { x: 0, y });
        if (!move) return;
        offset.setValue(move.dy);
        Animated.timing(offset, { toValue: 0, duration: MOTION_MS.fast + 60, easing: easeOut, useNativeDriver: true }).start();
      }}
    >
      {children}
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  confetti: { position: 'absolute', left: '50%', top: '30%', width: 0, height: 0, zIndex: 95 },
  piece: { position: 'absolute', width: 8, height: 12, borderRadius: 2 },
});
