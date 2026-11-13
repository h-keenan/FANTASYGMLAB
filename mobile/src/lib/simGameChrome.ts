import { useSyncExternalStore } from 'react';

/**
 * Whether the Fantasy Sim game is showing its own navigation orb (SimGameOrb).
 * The global GmOrb reads this and steps its floating button aside so two orbs
 * never stack; its search sheet stays mounted so search still opens. Mobile
 * only (web hides the global orb by path, bottomNav.pathOwnsPhoneChrome).
 */
let active = false;
const listeners = new Set<() => void>();

export const simGameChrome = {
  set(next: boolean): void {
    if (next === active) return;
    active = next;
    listeners.forEach((l) => l());
  },
  get: (): boolean => active,
  subscribe(listener: () => void): () => void {
    listeners.add(listener);
    return () => {
      listeners.delete(listener);
    };
  },
};

export function useSimGameOwnsOrb(): boolean {
  return useSyncExternalStore(simGameChrome.subscribe, simGameChrome.get, simGameChrome.get);
}
