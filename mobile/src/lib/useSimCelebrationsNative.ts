import AsyncStorage from '@react-native-async-storage/async-storage';
import { useCallback, useEffect, useState } from 'react';

import { SIM_CELEBRATIONS_KEY, simCelebrationsParse, simCelebrationsSerialize } from './simMoments.ts';

let current = true;
let loaded = false;
const listeners = new Set<(on: boolean) => void>();

function ensureLoaded(): void {
  if (loaded) return;
  loaded = true;
  AsyncStorage.getItem(SIM_CELEBRATIONS_KEY)
    .then((raw) => {
      current = simCelebrationsParse(raw);
      listeners.forEach((fn) => fn(current));
    })
    .catch(() => {});
}

/** The Celebrations setting (pick reveals, score roll-ins, win and loss stamps, streak badges). On by default; per device. */
export function useSimCelebrations(): [boolean, (on: boolean) => void] {
  const [on, setOn] = useState(current);
  useEffect(() => {
    listeners.add(setOn);
    ensureLoaded();
    setOn(current);
    return () => {
      listeners.delete(setOn);
    };
  }, []);
  const set = useCallback((next: boolean) => {
    current = next;
    listeners.forEach((fn) => fn(next));
    AsyncStorage.setItem(SIM_CELEBRATIONS_KEY, simCelebrationsSerialize(next)).catch(() => {});
  }, []);
  return [on, set];
}
