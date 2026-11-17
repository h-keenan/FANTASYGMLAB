import AsyncStorage from '@react-native-async-storage/async-storage';
import { useSyncExternalStore } from 'react';

import { createEffectsPrefs, type EffectsPrefs } from './effectsPrefsCore';

/** The one app-wide store for the "Haptics" and "Reduced effects" Settings toggles (device-local, persisted). */
export const effectsPrefs = createEffectsPrefs(AsyncStorage);
void effectsPrefs.load();

export function useEffectsPrefs(): EffectsPrefs {
  return useSyncExternalStore(effectsPrefs.subscribe, effectsPrefs.get, effectsPrefs.get);
}
