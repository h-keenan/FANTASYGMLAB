const EVENT = "fd:trade-outcome-answered";

/**
 * In-page signal that TradeOutcomePrompt just recorded a final answer
 * (yes / no / didn't send), so an open Trade History page can re-fetch and
 * show it without a reload. "Still pending" doesn't fire it: a snooze never
 * changes Trade History.
 */
export function emitTradeOutcomeAnswered(): void {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new Event(EVENT));
}

export function onTradeOutcomeAnswered(listener: () => void): () => void {
  if (typeof window === "undefined") return () => {};
  window.addEventListener(EVENT, listener);
  return () => window.removeEventListener(EVENT, listener);
}
