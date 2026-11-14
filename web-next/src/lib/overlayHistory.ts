import { planHistorySync, type OverlayStack } from "@/lib/overlayStack";

/**
 * Browser-history integration for the overlay stack (web). One history entry per open overlay, so the phone back
 * gesture / browser Back closes exactly the newest pop-up (the one below returns with its scroll and selections,
 * because hidden overlays stay mounted) instead of leaving the page.
 *
 * - A newly opened overlay pushes an entry (state carries the page's own history state, so the Next router's
 *   bookkeeping survives).
 * - A user Back (popstate) dismisses the newest overlay.
 * - Closing overlays in code (X, Back button, Escape) pops the entries it added, once per batch, and the resulting
 *   popstate is swallowed.
 * - `reset()` forgets our entries without touching history: used on a route change, where going back would leave
 *   the new page.
 * - A tap on an in-app link (or `markNavigating()`, for router.push) means the page is about to change. Closing the
 *   pop-up for that tap must NOT go back in history, or the Back undoes the navigation the tap just started (the
 *   "tapping a More-menu row does nothing" bug). The entries are forgotten instead; the route change closes the rest.
 */
export function isInAppNavigationClick(event: MouseEvent, origin: string): boolean {
  if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return false;
  const target = event.target as Element | null;
  const anchor = target && typeof target.closest === "function" ? (target.closest("a[href]") as HTMLAnchorElement | null) : null;
  if (!anchor || (anchor.target && anchor.target !== "_self") || anchor.hasAttribute("download")) return false;
  try {
    const url = new URL(anchor.href, origin);
    return url.origin === origin;
  } catch {
    return false;
  }
}

/** How long a tap on a link / markNavigating() keeps history Back suppressed (covers a slow route transition). */
const NAVIGATING_WINDOW_MS = 4000;

export function installOverlayHistory(stack: OverlayStack, win: Window = window): { dispose: () => void; reset: () => void; markNavigating: () => void } {
  let pushed = 0;
  let ignorePops = 0;
  let scheduled = false;
  let navigatingUntil = 0;
  const markNavigating = () => {
    navigatingUntil = Date.now() + NAVIGATING_WINDOW_MS;
  };
  const onClickCapture = (event: MouseEvent) => {
    if (stack.size() > 0 && isInAppNavigationClick(event, win.location.origin)) markNavigating();
  };
  win.document.addEventListener("click", onClickCapture, true);

  const sync = () => {
    scheduled = false;
    const plan = planHistorySync(pushed, stack.size());
    for (let i = 0; i < plan.push; i += 1) {
      pushed += 1;
      win.history.pushState({ ...(win.history.state ?? {}), fgOverlay: pushed }, "", win.location.href);
    }
    if (plan.pop > 0) {
      pushed -= plan.pop;
      if (Date.now() < navigatingUntil) return; // leaving the page: do not walk history back over the navigation
      ignorePops += 1;
      win.history.go(-plan.pop);
    }
  };
  // Batch: closing several overlays in one commit must produce one go(-n), hence one popstate to swallow.
  const schedule = () => {
    if (scheduled) return;
    scheduled = true;
    queueMicrotask(sync);
  };
  const unsubscribe = stack.subscribe(schedule);

  const onPopState = () => {
    if (ignorePops > 0) {
      ignorePops -= 1;
      return;
    }
    if (pushed > 0) {
      pushed -= 1;
      stack.back();
    }
  };
  win.addEventListener("popstate", onPopState);

  return {
    dispose() {
      unsubscribe();
      win.removeEventListener("popstate", onPopState);
      win.document.removeEventListener("click", onClickCapture, true);
    },
    reset() {
      pushed = 0;
      ignorePops = 0;
      navigatingUntil = 0;
    },
    markNavigating,
  };
}
