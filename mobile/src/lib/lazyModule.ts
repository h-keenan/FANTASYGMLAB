/**
 * Memoized lazy `require` for navigator screens.
 *
 * Metro bundles the whole app into one file, but with `inlineRequires` off a
 * static `import` makes the module run at launch, so RootNavigator used to
 * evaluate all ~40 screens (and everything only they import) before the first
 * frame, although a session opens one or two of them. Wrapping the screen's
 * `require` in a loader defers that evaluation to the first time the screen
 * renders (or to an idle-time preload, see `preloadInSequence`).
 *
 * See docs/performance-audit-client-2026-11.md.
 */
export interface LazyLoader<T> {
  /** Runs `load` on first call; every later call returns the same value. */
  get: () => T;
  isLoaded: () => boolean;
}

export function createLazyLoader<T>(load: () => T): LazyLoader<T> {
  let loaded = false;
  let value: T;
  return {
    get: () => {
      if (!loaded) {
        value = load();
        loaded = true;
      }
      return value;
    },
    isLoaded: () => loaded,
  };
}

/**
 * Warms loaders one per scheduled turn, so each module's evaluation is its own
 * short task instead of one long block. `schedule` runs a callback later
 * (setTimeout / InteractionManager in the app); a loader that throws is
 * reported and skipped, and never blocks the rest or the user (the screen
 * will surface the same error on demand if it is really opened).
 */
export function preloadInSequence(
  loaders: ReadonlyArray<LazyLoader<unknown>>,
  schedule: (run: () => void) => void,
  onError: (error: unknown) => void = () => {},
): void {
  const queue = loaders.filter((loader) => !loader.isLoaded());
  const step = () => {
    const next = queue.shift();
    if (!next) return;
    try {
      next.get();
    } catch (error) {
      onError(error);
    }
    if (queue.length > 0) schedule(step);
  };
  if (queue.length > 0) schedule(step);
}
