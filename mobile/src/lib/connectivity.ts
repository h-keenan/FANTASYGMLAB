// `.ts` extension on the import: this file is run directly by Node's test loader (see backgroundRetry.ts).
import { isAbortOrTimeoutError, isTransportError } from './transportError.ts';

/**
 * Connectivity state for the one shared offline banner (components/OfflineBanner.tsx).
 *
 * @react-native-community/netinfo is NOT installed in this app (adding a native module needs a new build), so
 * connectivity is inferred from the requests the app already makes: api.ts reports every outcome here. A bare
 * transport failure (no response at all) marks the app offline; any HTTP response, even a 5xx, proves the network
 * works and marks it online. While offline the banner polls GET /health to notice recovery without user action.
 * A timeout alone is "slow", not "offline", so it never raises the banner. When NetInfo is added, call
 * `setOffline(!state.isConnected)` from its listener and keep everything else. Web twin: navigator.onLine in
 * web-next/src/components/OfflineBanner.tsx.
 */

type Listener = (offline: boolean) => void;

let offline = false;
const listeners = new Set<Listener>();

export function isOffline(): boolean {
  return offline;
}

export function setOffline(next: boolean): void {
  if (offline === next) return;
  offline = next;
  for (const listener of [...listeners]) listener(offline);
}

export function subscribeConnectivity(listener: Listener): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

/** True for "the request never reached the server" (not a timeout, not a garbled body). */
export function looksOffline(err: unknown): boolean {
  if (isAbortOrTimeoutError(err) || !isTransportError(err)) return false;
  const message = err instanceof Error ? err.message : '';
  return !/timed? ?out|json|unexpected/i.test(message);
}

/** Called by api.ts for every request: a response of any status means online, a dead transport means offline. */
export function reportRequestOutcome(outcome: { responded: true } | { error: unknown }): void {
  if ('responded' in outcome) setOffline(false);
  else if (looksOffline(outcome.error)) setOffline(true);
}

/** Test helper: back to the initial state. */
export function resetConnectivityForTests(): void {
  offline = false;
  listeners.clear();
}
