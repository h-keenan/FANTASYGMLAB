/**
 * Trade side labels, shared by every trade surface (web `ExchangeSide`
 * callers use the same strings; CSS/`textTransform` uppercases them).
 * `send` pairs with the danger dot, `get`/`receive` with the success dot.
 * The Trade Analyzer says "receive" (web TradeAnalyzerContent); idea cards,
 * Dashboard, GM Plan and Finder say "get".
 */
export const TRADE_SIDE_LABEL = {
  send: 'You send',
  get: 'You get',
  receive: 'You receive',
} as const;

/** `#rrggbb` + alpha (0-1) as `#rrggbbaa`; RN has no color-mix. Non-hex input is returned unchanged. */
export function withAlpha(hex: string, alpha: number): string {
  if (!/^#[0-9a-fA-F]{6}$/.test(hex)) return hex;
  const a = Math.round(Math.max(0, Math.min(1, alpha)) * 255)
    .toString(16)
    .padStart(2, '0');
  return `${hex}${a}`;
}

/** The faint send/get wash behind a side's rows (web: color-mix 6% of the dot color). */
export const SIDE_TINT_ALPHA = 0.06;
