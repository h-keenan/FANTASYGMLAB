import React, { useEffect, useRef, useState } from 'react';
import { AccessibilityInfo, type StyleProp, type TextStyle } from 'react-native';

import AppText from './AppText';
import { useThemeMode } from '../context/ThemeModeContext';

const TICK_MS = 450;
const FLASH_MS = 1100;

/**
 * A number that counts to its new value (about 450 ms, ease-out) and flashes
 * green when it goes up. Reduced motion: no counting, the value just changes
 * and the (non-moving) green flash remains. First render never animates.
 * Twin of web-next/src/components/TickNumber.tsx.
 */
export default function TickNumber({
  value,
  decimals = 1,
  style,
  testID,
}: {
  value: number | null | undefined;
  decimals?: number;
  style?: StyleProp<TextStyle>;
  testID?: string;
}) {
  const { colors } = useThemeMode();
  const target = typeof value === 'number' && Number.isFinite(value) ? value : null;
  const [anim, setAnim] = useState<{ target: number; value: number } | null>(null);
  const [flashing, setFlashing] = useState(false);
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
    const instant = reduced.current;
    const start = Date.now();
    const step = () => {
      const t = instant ? 1 : Math.min(1, (Date.now() - start) / TICK_MS);
      const eased = 1 - (1 - t) ** 3;
      setAnim({ target, value: from + (target - from) * eased });
      if (t < 1) raf = requestAnimationFrame(step);
    };
    if (target > from) {
      setFlashing(true);
      flashTimer = setTimeout(() => setFlashing(false), FLASH_MS);
    }
    step();
    return () => {
      if (raf != null) cancelAnimationFrame(raf);
      if (flashTimer) clearTimeout(flashTimer);
    };
  }, [target]);

  const shown = anim && anim.target === target ? anim.value : target;
  return (
    <AppText
      testID={testID}
      style={[{ fontVariant: ['tabular-nums'] }, style, flashing && { color: colors.successBright }]}
    >
      {shown == null ? '—' : shown.toFixed(decimals)}
    </AppText>
  );
}
