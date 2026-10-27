/**
 * Wording shared by the trade share card on web (tradeCard.tsx) and mobile
 * (mobile/src/lib/tradeShareCopy.ts). These are the same words the in-app
 * Trade Hub card uses (TradeIdeaCard.tsx: "You send" / "You get" /
 * "Balance"), so the shared image reads like the screen it came from.
 * tradeCopy.test.ts keeps the mobile copy byte-identical to this block.
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
