"use client";

import dynamic from "next/dynamic";

// The post-trade check-in sheet only ever appears after a fetch finds a pending outcome, so its code (and the sheet-drag helpers it
// pulls in) loads after hydration instead of in every route's first-load JS.
const TradeOutcomePrompt = dynamic(() => import("@/components/TradeOutcomePrompt").then((m) => m.TradeOutcomePrompt), { ssr: false });

export function DeferredTradeOutcomePrompt() {
  return <TradeOutcomePrompt />;
}
