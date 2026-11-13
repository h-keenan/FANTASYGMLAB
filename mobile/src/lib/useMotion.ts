import { useEffect, useState } from 'react';
import { AccessibilityInfo } from 'react-native';

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
