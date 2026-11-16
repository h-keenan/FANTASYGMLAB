import React, { useEffect, useRef, useState } from 'react';
import { AccessibilityInfo, type StyleProp, type TextStyle } from 'react-native';

import AppText from './AppText';
import { useThemeMode } from '../context/ThemeModeContext';
import { COUNT_MS as TICK_MS, FLASH_MS, acquireTween, flashDirection } from '../lib/motion';


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
}: {
  value: number | null | undefined;
  decimals?: number;
  /** Formats the shown (in-between) value instead of `toFixed(decimals)` (money, signed gains). Round inside it. */
  format?: (n: number) => string;
  numberOfLines?: number;
  adjustsFontSizeToFit?: boolean;
  style?: StyleProp<TextStyle>;
  testID?: string;
}) {
  const { colors } = useThemeMode();
  const target = typeof value === 'number' && Number.isFinite(value) ? value : null;
  const [anim, setAnim] = useState<{ target: number; value: number } | null>(null);
  const [flashing, setFlashing] = useState<'up' | 'down' | null>(null);
  const previous = useRef<number | null>(target);
  const reduced = useRef(false);

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
  }, [target]);

  const shown = anim && anim.target === target ? anim.value : target;
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
