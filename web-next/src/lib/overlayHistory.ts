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
 */
export function installOverlayHistory(stack: OverlayStack, win: Window = window): { dispose: () => void; reset: () => void } {
  let pushed = 0;
  let ignorePops = 0;
  let scheduled = false;

  const sync = () => {
    scheduled = false;
    const plan = planHistorySync(pushed, stack.size());
    for (let i = 0; i < plan.push; i += 1) {
      pushed += 1;
      win.history.pushState({ ...(win.history.state ?? {}), fgOverlay: pushed }, "", win.location.href);
    }
    if (plan.pop > 0) {
      pushed -= plan.pop;
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
    },
    reset() {
      pushed = 0;
      ignorePops = 0;
    },
  };
}
