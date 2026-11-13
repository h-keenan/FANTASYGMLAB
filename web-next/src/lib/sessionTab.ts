// Shared (web + mobile twin): pure helpers for the shared Tabs component. The last tab a person used in a tabbed
// surface (a player sheet, a team sheet) is remembered for the session; where it is stored is the caller's choice
// (web sessionStorage, mobile an in-memory map), so this stays storage-agnostic and import-free.

export interface TabStore {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}

export const TAB_STORE_PREFIX = "fgl:tab:";

/** The tab to open: the remembered one when it still exists, else `initial` when valid, else the first tab. */
export function resolveTab(saved: string | null | undefined, keys: readonly string[], initial?: string): string {
  if (saved && keys.includes(saved)) return saved;
  if (initial && keys.includes(initial)) return initial;
  return keys[0] ?? "";
}

/** Which way a panel slides in: 1 when the new tab is to the right of the old one, -1 to the left, 0 for none. */
export function tabDirection(keys: readonly string[], from: string, to: string): -1 | 0 | 1 {
  const a = keys.indexOf(from);
  const b = keys.indexOf(to);
  if (a < 0 || b < 0 || a === b) return 0;
  return b > a ? 1 : -1;
}

/** Read the remembered tab; storage that throws (private windows, blocked site data) reads as nothing remembered. */
export function readSavedTab(store: TabStore | null | undefined, id: string): string | null {
  try {
    return store?.getItem(TAB_STORE_PREFIX + id) ?? null;
  } catch {
    return null;
  }
}

export function saveTab(store: TabStore | null | undefined, id: string, key: string): void {
  try {
    store?.setItem(TAB_STORE_PREFIX + id, key);
  } catch {
    // nothing remembered; the tabs still work
  }
}

/** An in-memory store (mobile app session, tests). */
export function createMemoryTabStore(): TabStore {
  const map = new Map<string, string>();
  return { getItem: (k) => map.get(k) ?? null, setItem: (k, v) => void map.set(k, v) };
}
