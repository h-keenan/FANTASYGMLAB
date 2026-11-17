import { useEffect } from 'react';
import { Easing, cancelAnimation, makeMutable, withRepeat, withTiming, type SharedValue } from 'react-native-reanimated';

import { AMBIENT_MS } from './motion';
import { useMotion } from './useMotion';

/**
 * ONE clock for every skeleton on screen (30 skeletons cost one UI-thread animation). 0 -> 1 linear over
 * AMBIENT_MS.shimmer, repeating. Reference counted: it starts with the first subscriber and stops (cancelled, value
 * reset) when the last skeleton unmounts, so nothing runs once content has loaded.
 */
const clock: SharedValue<number> = makeMutable(0);
let subscribers = 0;

function retain() {
  subscribers += 1;
  if (subscribers === 1) {
    clock.value = 0;
    clock.value = withRepeat(withTiming(1, { duration: AMBIENT_MS.shimmer, easing: Easing.linear }), -1, false);
  }
}
function release() {
  subscribers = Math.max(0, subscribers - 1);
  if (subscribers === 0) {
    cancelAnimation(clock);
    clock.value = 0;
  }
}

/** Subscribes to the shared clock; frozen (no subscription at all) under Reduce Motion or Reduced effects. */
export function useShimmerClock(): { clock: SharedValue<number>; running: boolean } {
  const { ambient } = useMotion();
  useEffect(() => {
    if (!ambient) return;
    retain();
    return release;
  }, [ambient]);
  return { clock, running: ambient };
}
