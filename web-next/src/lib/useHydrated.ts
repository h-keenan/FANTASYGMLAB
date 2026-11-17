import { useSyncExternalStore } from "react";

const subscribe = () => () => {};

/**
 * False during the server render AND the hydrating client render, true afterwards. Use it to gate anything that depends on client-only
 * state (a resolved auth session, localStorage, viewport) so the first client render matches the server HTML. useSyncExternalStore is
 * the one primitive that returns the server snapshot while hydrating even when other state updated before this boundary hydrated
 * (a Suspense boundary hydrates late, so plain useState/context values can already be "new" by then and cause React #418).
 */
export function useHydrated(): boolean {
  return useSyncExternalStore(subscribe, () => true, () => false);
}
