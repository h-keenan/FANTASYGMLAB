/**
 * Wording shared by the trade share card on mobile (TradeShareCard.tsx) and
 * web (web-next/src/lib/shareCard/tradeCopy.ts). Same words as the in-app
 * Trade Hub card. web-next's tradeCopy.test.ts keeps this block
 * byte-identical to web's.
 */
// BEGIN TRADE_SHARE_COPY
export const TRADE_SHARE_COPY = {
  send: "You send",
  get: "You get",
  pitchSend: "I send",
  pitchGet: "I get",
  balance: "Balance",
  value: "Value",
  even: "Even",
} as const;
// END TRADE_SHARE_COPY

export const LOW_CONFIDENCE_NOTE = 'More dependent on partner preference and market fit.';
