import { useEffect, useRef, useSyncExternalStore } from "react";

import { normalizeHeaderChips, type HeaderChip } from "@/lib/appHeader";

/**
 * The page -> header channel (web), the twin of lib/bottomPillStore.ts: a page registers the glanceable chips for the header's context
 * ribbon (week, record, odds). Module-level on purpose (the page and the header live in different branches of the tree). A page that
 * unmounts clears its chips, but only if it still owns them, so navigating between two pages never shows the old page's chips.
 */
let owner: object | null = null;
let chips: HeaderChip[] = [];
const listeners = new Set<() => void>();
const EMPTY: HeaderChip[] = [];

const sig = (c: HeaderChip[]) => c.map((x) => `${x.key}|${x.text}|${x.tone ?? ""}`).join("~");

export function setHeaderChips(who: object, next: ReadonlyArray<HeaderChip | null | undefined> | null, avoid: ReadonlyArray<string | null | undefined> = []) {
  if (next === null) {
    if (owner !== who) return;
    owner = null;
    if (chips.length === 0) return;
    chips = EMPTY;
    listeners.forEach((l) => l());
    return;
  }
  owner = who;
  const normalized = normalizeHeaderChips(next, avoid);
  if (sig(normalized) === sig(chips)) return;
  chips = normalized.length ? normalized : EMPTY;
  listeners.forEach((l) => l());
}

function subscribe(l: () => void) {
  listeners.add(l);
  return () => {
    listeners.delete(l);
  };
}

/** The chips the header ribbon shows right now. */
export function useHeaderChips(): HeaderChip[] {
  return useSyncExternalStore(subscribe, () => chips, () => EMPTY);
}

/** Pages call this with their ribbon chips; `avoid` lists labels the chips must not repeat (the page's own name). */
export function useHeaderContext(next: ReadonlyArray<HeaderChip | null | undefined>, avoid: ReadonlyArray<string | null | undefined> = []) {
  const who = useRef<object>({});
  const key = next.map((c) => (c ? `${c.key}|${c.text}|${c.tone ?? ""}` : "")).join("~") + "#" + avoid.join("~");
  useEffect(() => {
    setHeaderChips(who.current, next, avoid);
    // `key` is the dependency on purpose: it is the content signature of `next` and `avoid`.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  useEffect(() => {
    const me = who.current;
    return () => setHeaderChips(me, null);
  }, []);
}

/** Test helper. */
export function resetHeaderChips() {
  owner = null;
  chips = EMPTY;
  listeners.forEach((l) => l());
}
