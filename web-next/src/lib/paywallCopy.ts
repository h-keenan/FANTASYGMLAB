/**
 * Paywall copy shared by web (/premium, onboarding trial offer) and mobile
 * (PaywallScreen). Byte-identical to mobile/src/lib/paywallCopy.ts (twin
 * check + test). Names come from lib/terms.ts: Today, GM Plan, Pro.
 *
 * Numbers are never typed here: highlight bodies are built from the server's
 * enforced Free-vs-Pro rows (premium_comparison), and the savings percent is
 * computed from the two real prices the store/Stripe returned.
 */
export const PAYWALL_HERO_TITLE = "Make the right call every week";
export const PAYWALL_HERO_SUB =
  "Free already gives you real recommendations. Pro removes the caps, so you see every move, every trade idea and the whole waiver board.";

export type HighlightIcon = "today" | "trades" | "waivers";

export interface ProHighlight {
  key: string;
  icon: HighlightIcon;
  title: string;
  body: string;
}

export interface ComparisonRowLike {
  key: string;
  free: string;
  pro: string;
}

function freeLimit(rows: ComparisonRowLike[], key: string, fallback: string): string {
  const row = rows.find((r) => r.key === key);
  return (row?.free || fallback).trim().toLowerCase();
}

/** The three headline benefits, with the real Free limit in each line. */
export function proHighlights(rows: ComparisonRowLike[]): ProHighlight[] {
  return [
    {
      key: "today",
      icon: "today",
      title: "Your whole Today briefing",
      body: `Free shows the ${freeLimit(rows, "next_moves", "top 4")}. Pro shows every move worth making.`,
    },
    {
      key: "trades",
      icon: "trades",
      title: "Every trade idea",
      body: `Free shows the ${freeLimit(rows, "trade_hub", "first 2")}. Pro shows all of them, ranked for your roster.`,
    },
    {
      key: "waivers",
      icon: "waivers",
      title: "The full waiver board",
      body: "Stash candidates, deeper watchlist and a FAAB shortlist, not just the priority adds.",
    },
  ];
}

/** "$9.99" / "9.99" / "USD 9.99" -> 9.99; null when no number is present. */
export function parsePrice(value: string | number | null | undefined): number | null {
  if (typeof value === "number") return Number.isFinite(value) && value > 0 ? value : null;
  const match = /(\d+(?:[.,]\d{1,2})?)/.exec(String(value ?? "").replace(/,(?=\d{3}\b)/g, ""));
  if (!match) return null;
  const n = Number(match[1].replace(",", "."));
  return Number.isFinite(n) && n > 0 ? n : null;
}

/** Whole-number percent saved by paying yearly instead of 12 monthly payments; null when not a saving. */
export function annualSavingsPercent(monthly: string | number | null | undefined, annual: string | number | null | undefined): number | null {
  const m = parsePrice(monthly);
  const a = parsePrice(annual);
  if (m === null || a === null) return null;
  const pct = Math.round((1 - a / (m * 12)) * 100);
  return pct > 0 ? pct : null;
}

export const PAYWALL_TRIAL_REASSURANCE = "Cancel anytime. You can switch plans or stop whenever you like.";
export const PAYWALL_CARD_NOTE = "The Pro trial needs a card. The free plan never does.";
export const PAYWALL_COMPARISON_TITLE = "Everything in Pro";
