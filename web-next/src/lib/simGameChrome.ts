import { useSyncExternalStore } from "react";

/**
 * Whether the Fantasy Sim is drawing its own bottom stack (game orb + action bar) right now. Only the in-game
 * screens do; the hub, setup, loading and error screens have none, so the global GM orb / shell bar must show there.
 * Mirrors mobile/src/lib/simGameChrome.ts. See bottomNav.pathOwnsPhoneChrome.
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
  return useSyncExternalStore(simGameChrome.subscribe, simGameChrome.get, () => false);
}
