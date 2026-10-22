const KEY = "fd:trade-outcome-prompt-dismissed";

/**
 * Web-only session cap for TradeOutcomePrompt. Mobile's prompt is a modal
 * with no close button (every exit is one of the four answers), so it has
 * no client-side dismiss state at all. The web version is a small,
 * non-blocking card with a close button, so closing it needs somewhere to
 * live: sessionStorage, which keeps the prompt from coming back for the
 * rest of this browser session (tab) and clears when the tab closes.
 *
 * Closing the card never writes to the server. It is not an answer, and it
 * is not the "Still pending" snooze. The row stays pending, so the next
 * session (or the phone) still asks about it.
 *
 * Every storage access is wrapped in try/catch. It can throw in a private
 * window or with site data blocked, and the worst case is the card showing
 * again, never a broken page.
 */
export function isTradeOutcomePromptDismissed(): boolean {
  try {
    return window.sessionStorage.getItem(KEY) === "1";
  } catch {
    return false;
  }
}

export function setTradeOutcomePromptDismissed(): void {
  try {
    window.sessionStorage.setItem(KEY, "1");
  } catch {
    // Best-effort; the component's own state still hides it for this page.
  }
}
