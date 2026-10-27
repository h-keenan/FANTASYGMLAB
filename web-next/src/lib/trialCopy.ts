import type { BillingPlan, BillingTrial } from "@/lib/api";

/** "$3.99" + "per month" -> "$3.99/month". Falls back to the raw cadence text. */
export function priceWithCadence(plan: Pick<BillingPlan, "price" | "cadence">): string {
  const unit = plan.cadence.replace(/^per\s+/i, "").trim();
  return unit ? `${plan.price}/${unit}` : plan.price;
}

/** Trial copy only when the server says this account can actually get the trial. */
export function activeTrialDays(trial: BillingTrial | null | undefined): number {
  return trial && trial.eligible && trial.days > 0 ? trial.days : 0;
}

export function trialCtaLabel(days: number): string {
  return `Start ${days}-day free trial`;
}

export function thenPriceLine(plan: Pick<BillingPlan, "price" | "cadence">): string {
  return `Then ${priceWithCadence(plan)}. Cancel anytime.`;
}

/** "Trial ends Oct 25", or "" when there is no future trial end. */
export function trialEndLabel(iso: string | null | undefined, now: Date = new Date()): string {
  if (!iso) return "";
  const end = new Date(iso);
  if (Number.isNaN(end.getTime()) || end.getTime() <= now.getTime()) return "";
  return `Trial ends ${end.toLocaleDateString("en-US", { month: "short", day: "numeric" })}`;
}

/** Honest card disclosure: the Stripe trial collects a card up front; the free plan never does. */
export const TRIAL_CARD_NOTE = "The Premium trial needs a card and you can cancel anytime. The free plan needs no card.";
