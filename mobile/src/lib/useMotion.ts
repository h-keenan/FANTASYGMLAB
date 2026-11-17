import { useEffect, useState } from 'react';
import { AccessibilityInfo } from 'react-native';

import { useEffectsPrefs } from './effectsPrefs';
import { SPRING, motionMs, type MotionSpeed, type SpringName } from './motion';

/** The reduced-motion switch (OS "Reduce Motion"). Live: follows the setting if it changes while the app is open. */
export function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    let active = true;
    AccessibilityInfo.isReduceMotionEnabled()
      .then((value) => {
        if (active) setReduced(Boolean(value));
      })
      .catch(() => {});
    const sub = AccessibilityInfo.addEventListener('reduceMotionChanged', (value) => setReduced(Boolean(value)));
    return () => {
      active = false;
      sub?.remove?.();
    };
  }, []);
  return reduced;
}

/**
 * The shared motion switch for the app's primitives (docs/design/app-motion-plan.md, 2.3). `reduced` = OS Reduce Motion:
 * entrances, springs and tickers collapse to final values. `reducedEffects` = the Settings "Reduced effects" toggle:
 * ambient loops (shimmer sweep, breathing), parallax and blur animation turn off, while ordinary feedback stays.
 * `ambient` is true only when neither is on. Primitives read this; screens never branch on it themselves.
 */
export function useMotion(): {
  reduced: boolean;
  reducedEffects: boolean;
  ambient: boolean;
  ms: (speed: MotionSpeed | number) => number;
  spring: (name: SpringName) => (typeof SPRING)[SpringName];
} {
  const reduced = useReducedMotion();
  const { reducedEffects } = useEffectsPrefs();
  return {
    reduced,
    reducedEffects,
    ambient: !reduced && !reducedEffects,
    ms: (speed) => motionMs(speed, reduced),
    spring: (name) => SPRING[name],
  };
}
