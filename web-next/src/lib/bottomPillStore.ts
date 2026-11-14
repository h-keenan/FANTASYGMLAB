import { normalizePillContext, type PillContext } from "@/lib/bottomNav";

/**
 * The page -> pill channel (web). A page registers its context (useBottomPillContext); the shell's pill subscribes.
 * Module-level on purpose: the page and the bar live in different branches of the tree and a provider would add a
 * re-render path through the whole app. Callbacks are proxied so the pill always calls the page's latest closure
 * without re-rendering on every page render; only a change in what is SHOWN (id, tabs, lit tab, primary) notifies.
 */
export type PillState = { ctx: PillContext | null; barPresent: boolean };

let owner: object | null = null;
let latest: PillContext | null = null;
let clearTimer: ReturnType<typeof setTimeout> | null = null;
/** A page that unmounts as the next family page mounts must not flash the plain global tabs in between. */
export const PILL_CLEAR_DELAY_MS = 300;
let state: PillState = { ctx: null, barPresent: false };
const listeners = new Set<() => void>();

const signature = (c: PillContext | null) =>
  c ? JSON.stringify([c.id, c.label, c.activeKey, c.tabs.map((t) => [t.key, t.label, t.glyph, t.badge, t.href]), c.primary && [c.primary.key, c.primary.label, c.primary.glyph, c.primary.disabled, c.primary.busy, c.primary.href]]) : "";

function publish(next: PillState) {
  const changed = signature(next.ctx) !== signature(state.ctx) || next.barPresent !== state.barPresent;
  if (!changed) return;
  state = next;
  listeners.forEach((l) => l());
}

function proxied(ctx: PillContext | null): PillContext | null {
  const n = normalizePillContext(ctx);
  if (!n) return null;
  return {
    ...n,
    onSelect: (key) => latest?.onSelect(key),
    primary: n.primary ? { ...n.primary, onPress: () => latest?.primary?.onPress() } : undefined,
  };
}

/** Register (or update) the context owned by `who`. Pass null to clear it (only if `who` still owns it). */
export function setPillContext(who: object, ctx: PillContext | null) {
  if (!ctx) {
    if (owner === who) {
      owner = null;
      latest = null;
      if (clearTimer) clearTimeout(clearTimer);
      clearTimer = setTimeout(() => {
        clearTimer = null;
        if (owner === null) publish({ ...state, ctx: null });
      }, PILL_CLEAR_DELAY_MS);
    }
    return;
  }
  if (clearTimer) {
    clearTimeout(clearTimer);
    clearTimer = null;
  }
  owner = who;
  latest = ctx;
  publish({ ...state, ctx: proxied(ctx) });
}

export function setPillBarPresent(present: boolean) {
  publish({ ...state, barPresent: present });
}

export const subscribePill = (l: () => void) => {
  listeners.add(l);
  return () => void listeners.delete(l);
};
export const getPillState = () => state;
export const getServerPillState = (): PillState => ({ ctx: null, barPresent: false });
/** Test helper. */
export function resetPillStore() {
  owner = null;
  latest = null;
  if (clearTimer) clearTimeout(clearTimer);
  clearTimer = null;
  state = { ctx: null, barPresent: false };
  listeners.clear();
}
