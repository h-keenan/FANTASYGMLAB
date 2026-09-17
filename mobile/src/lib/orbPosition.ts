import AsyncStorage from '@react-native-async-storage/async-storage';
import { useEffect, useState } from 'react';

const KEY = 'fgl:orb-horizontal-fraction';

/**
 * Horizontal-only drag position for GmOrb, persisted per device as a
 * fraction (-1 = as far left as the safe area allows, 0 = centered/default,
 * 1 = as far right as allowed) of whichever side's available travel
 * applies — NOT a raw pixel offset. A pixel value saved on one window size
 * is wrong on the next: `supportsTablet` is true, so this app runs in iPad
 * split view and Stage Manager, where the window resizes at runtime, and
 * rotation does the same. That's the same shape of mistake as picking the
 * inset clamp ceiling from one measured device (see PR #513's history) —
 * a number that's right on the device it was set on and wrong everywhere
 * else. The caller converts this fraction to pixels against the CURRENT
 * bounds on every render, so it re-clamps automatically as the window
 * changes instead of needing a resize/rotation listener.
 */
export function useOrbHorizontalFraction(): [number, (next: number) => void] {
  const [fraction, setFractionState] = useState(0);

  useEffect(() => {
    let cancelled = false;
    AsyncStorage.getItem(KEY)
      .then((raw) => {
        if (cancelled || !raw) return;
        const parsed = Number(raw);
        if (Number.isFinite(parsed)) setFractionState(Math.min(1, Math.max(-1, parsed)));
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  const setFraction = (next: number) => {
    const clamped = Math.min(1, Math.max(-1, next));
    setFractionState(clamped);
    AsyncStorage.setItem(KEY, String(clamped)).catch(() => {});
  };

  return [fraction, setFraction];
}
