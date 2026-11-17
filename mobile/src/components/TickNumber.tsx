import React, { useEffect, useRef, useState } from 'react';
import { AccessibilityInfo, StyleSheet, View, type StyleProp, type TextStyle } from 'react-native';
import Animated, { Easing, useAnimatedStyle, useSharedValue, withTiming } from 'react-native-reanimated';

import AppText from './AppText';
import { useThemeMode } from '../context/ThemeModeContext';
import { COUNT_MS as TICK_MS, EASE, FLASH_MS, HERO_MS, MAX_CONCURRENT_TWEENS, acquireTween, activeTweenCount, flashDirection } from '../lib/motion';
import { useReducedMotion } from '../lib/useMotion';

const rollEase = Easing.bezier(...EASE.emphasized);

/**
 * One character of a rolling number. When the character changes, the old glyph slides out and the new one slides in
 * (translateY + opacity on the UI thread, clipped to one line). Sized by an invisible copy of the current glyph.
 */
function RollChar({ char, dir, animate, lh, style }: { char: string; dir: 1 | -1; animate: boolean; lh: number; style: StyleProp<TextStyle> }) {
  const previous = useRef(char);
  const [old, setOld] = useState<string | null>(null);
  const progress = useSharedValue(1);
  useEffect(() => {
    if (previous.current === char) return;
    const from = previous.current;
    previous.current = char;
    if (!animate) {
      setOld(null);
      progress.value = 1;
      return;
    }
    setOld(from);
    progress.value = 0;
    progress.value = withTiming(1, { duration: HERO_MS.hero, easing: rollEase });
  }, [char, animate, progress]);
  const incoming = useAnimatedStyle(() => ({ opacity: progress.value, transform: [{ translateY: (1 - progress.value) * lh * dir }] }));
  const outgoing = useAnimatedStyle(() => ({ opacity: 1 - progress.value, transform: [{ translateY: -progress.value * lh * dir }] }));
  const glyph = [style, { lineHeight: lh }];
  return (
    <View style={{ height: lh, overflow: 'hidden' }}>
      <AppText style={[glyph, { opacity: 0 }]}>{char}</AppText>
      {old != null ? (
        <Animated.View pointerEvents="none" style={[StyleSheet.absoluteFill, outgoing]}>
          <AppText style={glyph}>{old}</AppText>
        </Animated.View>
      ) : null}
      <Animated.View pointerEvents="none" style={[StyleSheet.absoluteFill, incoming]}>
        <AppText style={glyph}>{char}</AppText>
      </Animated.View>
    </View>
  );
}


/**
 * A number that counts to its new value (about 450 ms, ease-out) and flashes
 * green when it goes up and red when it goes down. Reduced motion: no counting, the value just changes
 * and the (non-moving) green flash remains. First render never animates.
 * Twin of web-next/src/components/TickNumber.tsx.
 */
export default function TickNumber({
  value,
  decimals = 1,
  format,
  numberOfLines,
  adjustsFontSizeToFit,
  style,
  testID,
  variant = 'count',
}: {
  value: number | null | undefined;
  decimals?: number;
  /** Formats the shown (in-between) value instead of `toFixed(decimals)` (money, signed gains). Round inside it. */
  format?: (n: number) => string;
  numberOfLines?: number;
  adjustsFontSizeToFit?: boolean;
  style?: StyleProp<TextStyle>;
  testID?: string;
  /** `count` (default) tweens through the in-between values; `roll` slides each changed digit like an odometer (UI thread). */
  variant?: 'count' | 'roll';
}) {
  const { colors } = useThemeMode();
  const target = typeof value === 'number' && Number.isFinite(value) ? value : null;
  const [anim, setAnim] = useState<{ target: number; value: number } | null>(null);
  const [flashing, setFlashing] = useState<'up' | 'down' | null>(null);
  const previous = useRef<number | null>(target);
  const reduced = useRef(false);
  const osReduced = useReducedMotion();
  const roll = variant === 'roll' && !adjustsFontSizeToFit && !numberOfLines;
  // Roll direction and whether to animate are decided during render (before the digits' own effects run).
  const rollRef = useRef<{ seen: number | null; dir: 1 | -1; animate: boolean }>({ seen: target, dir: 1, animate: false });
  if (roll && rollRef.current.seen !== target) {
    const prev = rollRef.current.seen;
    rollRef.current = {
      seen: target,
      dir: prev != null && target != null && target < prev ? -1 : 1,
      animate: !osReduced && prev != null && target != null && activeTweenCount() < MAX_CONCURRENT_TWEENS,
    };
  }
  const rollState = rollRef.current;

  useEffect(() => {
    void AccessibilityInfo.isReduceMotionEnabled().then((enabled) => {
      reduced.current = enabled;
    });
  }, []);

  useEffect(() => {
    const from = previous.current;
    previous.current = target;
    if (target == null || from == null || from === target) return;
    let raf: ReturnType<typeof requestAnimationFrame> | null = null;
    let flashTimer: ReturnType<typeof setTimeout> | null = null;
    if (roll) {
      // The roll runs on the UI thread; it still takes one of the 12 tween slots so a screen full of live numbers
      // degrades to a plain change. Only the flash is JS-timed (one timeout).
      const slot = acquireTween();
      const dir = flashDirection(from, target);
      const slotTimer = slot ? setTimeout(slot, HERO_MS.hero) : null;
      if (dir) {
        setFlashing(dir);
        flashTimer = setTimeout(() => setFlashing(null), FLASH_MS);
      }
      return () => {
        if (slotTimer) clearTimeout(slotTimer);
        slot?.();
        if (flashTimer) clearTimeout(flashTimer);
      };
    }
    // At most MAX_CONCURRENT_TWEENS number tweens run at once; past that the value just changes (the flash still plays).
    const release = acquireTween();
    const instant = reduced.current || release === null;
    const start = Date.now();
    const step = () => {
      const t = instant ? 1 : Math.min(1, (Date.now() - start) / TICK_MS);
      const eased = 1 - (1 - t) ** 3;
      setAnim({ target, value: from + (target - from) * eased });
      if (t < 1) raf = requestAnimationFrame(step);
      else release?.();
    };
    const dir = flashDirection(from, target);
    if (dir) {
      setFlashing(dir);
      flashTimer = setTimeout(() => setFlashing(null), FLASH_MS);
    }
    step();
    return () => {
      if (raf != null) cancelAnimationFrame(raf);
      release?.();
      if (flashTimer) clearTimeout(flashTimer);
    };
  }, [target, roll, osReduced]);

  const shown = anim && anim.target === target ? anim.value : target;
  if (roll) {
    const text = target == null ? '—' : format ? format(target) : target.toFixed(decimals);
    const flat = StyleSheet.flatten(style) ?? {};
    const lh = Math.round((typeof flat.fontSize === 'number' ? flat.fontSize : 16) * 1.25);
    const glyphStyle: StyleProp<TextStyle> = [
      { fontVariant: ['tabular-nums'] },
      style,
      flashing === 'up' && { color: colors.successBright },
      flashing === 'down' && { color: colors.danger },
    ];
    const chars = Array.from(text);
    return (
      <View testID={testID} accessible accessibilityRole="text" accessibilityLabel={text} style={{ flexDirection: 'row', alignItems: 'center' }}>
        {chars.map((ch, i) => {
          // Keyed from the right so the ones digit keeps its identity when a leading digit appears or goes.
          const key = chars.length - i;
          return /\d/.test(ch) ? (
            <RollChar key={key} char={ch} dir={rollState.dir} animate={rollState.animate} lh={lh} style={glyphStyle} />
          ) : (
            <AppText key={key} style={[glyphStyle, { lineHeight: lh }]}>
              {ch}
            </AppText>
          );
        })}
      </View>
    );
  }
  return (
    <AppText
      testID={testID}
      numberOfLines={numberOfLines}
      adjustsFontSizeToFit={adjustsFontSizeToFit}
      style={[{ fontVariant: ['tabular-nums'] }, style, flashing === 'up' && { color: colors.successBright }, flashing === 'down' && { color: colors.danger }]}
    >
      {shown == null ? '—' : format ? format(shown) : shown.toFixed(decimals)}
    </AppText>
  );
}
