// THE overlay stack (web + mobile, byte-identical twin): the single source of truth for which pop-up is on screen.
//
// Rule (coridian_, approved): one pop-up on screen at a time. Opening a pop-up from inside another one REPLACES it on
// screen: the first stays mounted but hidden (so its scroll, selections and drafts survive) and returns when the newer
// one goes away. The newer one gets "‹ Back to <title>"; the phone back gesture / browser back (web) or Android back
// (mobile) goes back one step; the X closes everything. A real dialog (sign out, a destructive confirm that cannot
// live in-place) is kind "dialog": it sits ON TOP of the visible sheet without hiding it, and closing it returns to the
// sheet underneath. Toasts are not overlays and never register here.
//
// Pure module (no React, no DOM, no timers) so both platforms and the tests share the exact same rules.

export type OverlayKind = "sheet" | "dialog";

export type OverlayEntry = {
  id: string;
  kind: OverlayKind;
  /** Shown in the Back button of the overlay opened from this one ("‹ Back to Trade picker"). */
  title: string;
  /** Close this overlay (the owner flips its own `open` state). Called by back / close-all / the browser back button. */
  dismiss: () => void;
};

export type OverlayStack = {
  /** Register an overlay as the newest. Idempotent per id (a re-open with the same id keeps its place, refreshes dismiss/title). */
  open(entry: OverlayEntry): void;
  /** Remove an overlay wherever it is; the one below becomes visible again. */
  close(id: string): void;
  entries(): readonly OverlayEntry[];
  size(): number;
  /** The newest overlay of any kind: it owns focus and Escape. */
  top(): OverlayEntry | null;
  /** The newest sheet: the one sheet that is visible. */
  topSheet(): OverlayEntry | null;
  /** A sheet that is open but hidden behind a newer sheet. Dialogs never hide anything and are never hidden. */
  isHidden(id: string): boolean;
  /** This overlay is the newest (focus trap / Escape belong to it). */
  isTop(id: string): boolean;
  /** The sheet directly below this sheet, or null: what "‹ Back to ..." returns to. */
  previousSheet(id: string): OverlayEntry | null;
  /** Layer for z-ordering: dialogs always above sheets. */
  layer(id: string): number;
  /** Close the newest overlay (back gesture, browser back, Escape). Returns what was dismissed, or null when empty. */
  back(): OverlayEntry | null;
  /** Close every overlay, newest first (the X). Returns the ids dismissed. */
  closeAll(): string[];
  subscribe(listener: () => void): () => void;
  /** Snapshot token that changes whenever the stack does (for useSyncExternalStore). */
  version(): number;
};

/** z-index per layer; toasts (100) sit above both. Mirrored by --z-overlay-* in globals.css. */
export const OVERLAY_Z = { sheet: 70, dialog: 90, toast: 100 } as const;

export function createOverlayStack(): OverlayStack {
  let list: OverlayEntry[] = [];
  let version = 0;
  const listeners = new Set<() => void>();
  const emit = () => {
    version += 1;
    listeners.forEach((listener) => listener());
  };
  const index = (id: string) => list.findIndex((e) => e.id === id);
  const sheets = () => list.filter((e) => e.kind === "sheet");

  return {
    open(entry) {
      const at = index(entry.id);
      if (at >= 0) {
        const prev = list[at];
        if (prev.dismiss === entry.dismiss && prev.title === entry.title && prev.kind === entry.kind) return;
        list = list.map((e, i) => (i === at ? { ...entry } : e));
        emit();
        return;
      }
      list = [...list, { ...entry }];
      emit();
    },
    close(id) {
      if (index(id) < 0) return;
      list = list.filter((e) => e.id !== id);
      emit();
    },
    entries: () => list,
    size: () => list.length,
    top: () => (list.length ? list[list.length - 1] : null),
    topSheet() {
      const s = sheets();
      return s.length ? s[s.length - 1] : null;
    },
    isHidden(id) {
      const entry = list[index(id)];
      if (!entry || entry.kind !== "sheet") return false;
      const s = sheets();
      return s[s.length - 1].id !== id;
    },
    isTop: (id) => list.length > 0 && list[list.length - 1].id === id,
    previousSheet(id) {
      const s = sheets();
      const at = s.findIndex((e) => e.id === id);
      return at > 0 ? s[at - 1] : null;
    },
    layer(id) {
      const entry = list[index(id)];
      return entry?.kind === "dialog" ? OVERLAY_Z.dialog : OVERLAY_Z.sheet;
    },
    back() {
      const entry = list.length ? list[list.length - 1] : null;
      if (entry) entry.dismiss();
      return entry;
    },
    closeAll() {
      const dismissed: string[] = [];
      for (const entry of [...list].reverse()) {
        dismissed.push(entry.id);
        entry.dismiss();
      }
      return dismissed;
    },
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
export const overlayStack: OverlayStack = createOverlayStack();

/**
 * How many browser-history entries to add or drop so history depth equals overlay depth (web). One entry per open
 * overlay means the browser/phone back button always closes exactly the newest one. `pushed` is how many entries this
 * module has added so far.
 */
export function planHistorySync(pushed: number, size: number): { push: number; pop: number } {
  if (size > pushed) return { push: size - pushed, pop: 0 };
  if (size < pushed) return { push: 0, pop: pushed - size };
  return { push: 0, pop: 0 };
}
