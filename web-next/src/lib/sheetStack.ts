// Sheet stacking rule shared by web-next's and mobile's `Sheet`: sheets never
// stack on screen. When a second sheet opens while one is already showing, the
// first one is HIDDEN (kept mounted so its state, scroll and drafts survive)
// and comes back when the newer one closes. Only the top sheet is visible,
// traps focus and owns the Escape key.
//
// Pure module (no React, no DOM) so both platforms and the tests use the same
// code; the components subscribe through `useSyncExternalStore`.

export type SheetStack = {
  /** Register a sheet as the newest (top) one. Idempotent per id. */
  open(id: string): void;
  /** Remove a sheet; the previous one becomes the top again. */
  close(id: string): void;
  /** The id of the visible sheet, or null when none is open. */
  top(): string | null;
  /** How many sheets are open (visible + hidden). */
  size(): number;
  /** True when the sheet is open but hidden behind a newer one. */
  isHidden(id: string): boolean;
  subscribe(listener: () => void): () => void;
  /** Snapshot token that changes whenever the stack does (for useSyncExternalStore). */
  version(): number;
};

export function createSheetStack(): SheetStack {
  let ids: string[] = [];
  let version = 0;
  const listeners = new Set<() => void>();
  const emit = () => {
    version += 1;
    listeners.forEach((listener) => listener());
  };
  return {
    open(id) {
      if (ids.includes(id)) return;
      ids = [...ids, id];
      emit();
    },
    close(id) {
      if (!ids.includes(id)) return;
      ids = ids.filter((existing) => existing !== id);
      emit();
    },
    top: () => (ids.length ? ids[ids.length - 1] : null),
    size: () => ids.length,
    isHidden: (id) => ids.includes(id) && ids[ids.length - 1] !== id,
    subscribe(listener) {
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    },
    version: () => version,
  };
}

/** The one stack the app uses. */
export const sheetStack: SheetStack = createSheetStack();
