/**
 * Registry of in-memory caches that hold account or league data (byte-identical lib twin, imports nothing).
 * A module that keeps a module-level Map of fetched data registers a reset here; the account purge calls
 * `resetAccountCaches()` so nothing fetched for user A can be served to user B in the same session.
 * Audit: docs/audits/2026-11-account-isolation.md.
 */
const resets = new Set<() => void>();

/** Registers a cache reset; returns an unregister function. */
export function registerAccountCacheReset(reset: () => void): () => void {
  resets.add(reset);
  return () => {
    resets.delete(reset);
  };
}

/** Runs every registered reset. A throwing reset never stops the others. */
export function resetAccountCaches(): void {
  for (const reset of [...resets]) {
    try {
      reset();
    } catch {
      /* keep going */
    }
  }
}
