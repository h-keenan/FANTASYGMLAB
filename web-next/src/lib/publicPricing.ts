import type { BillingPlan } from "@/lib/api";
import { env } from "@/lib/env";
import { FALLBACK_PLAN_PRICES } from "@/lib/planPrices.generated";

/**
 * Plans for a LOGGED-OUT visitor (P0 UX audit, 2026-10-27): /premium used to
 * `router.replace("/")` anyone without a session, so there was no public
 * pricing page at all. api.getBillingPlans() can't be reused here -- it's
 * `authorizedBillingRequest`, which 401s without a session -- but the
 * underlying Supabase Edge Function (supabase/functions/billing-plans) is
 * explicitly public (its own comment: "works without a session (landing
 * page)"); fetchPublicTrialDays (lib/landingTrial.ts) already calls it the
 * same unauthenticated way for the trial-length line on "/". This mirrors
 * that, but keeps the full plan list (label/price/cadence/features)
 * instead of just trial_days.
 *
 * Resolves to null on any failure, or when NEXT_PUBLIC_BILLING_BACKEND is
 * "fastapi" (that rollback route requires auth, same as fetchPublicTrialDays)
 * -- callers fall back to FALLBACK_PUBLIC_PLANS so the page still shows
 * something useful instead of breaking.
 */
export async function fetchPublicBillingPlans(signal?: AbortSignal): Promise<BillingPlan[] | null> {
  if (process.env.NEXT_PUBLIC_BILLING_BACKEND === "fastapi") return null;
  const base = (env.supabaseUrl ?? "").replace(/\/+$/, "");
  const anonKey = env.supabaseAnonKey ?? "";
  if (!base || !anonKey) return null;
  try {
    const response = await fetch(`${base}/functions/v1/billing-plans`, {
      headers: { apikey: anonKey },
      signal,
    });
    if (!response.ok) return null;
    const body = (await response.json()) as { plans?: unknown };
    if (!Array.isArray(body.plans)) return null;
    const plans = body.plans.filter(
      (p): p is BillingPlan =>
        !!p &&
        typeof p === "object" &&
        typeof (p as BillingPlan).tier === "string" &&
        typeof (p as BillingPlan).interval === "string" &&
        typeof (p as BillingPlan).label === "string" &&
        typeof (p as BillingPlan).price === "string" &&
        typeof (p as BillingPlan).cadence === "string" &&
        Array.isArray((p as BillingPlan).features),
    );
    return plans.length > 0 ? plans : null;
  } catch {
    return null;
  }
}

const FALLBACK_FEATURES = [
  "Your full Next Move briefing, not just the top 4",
  "League Pulse leaders — your league's top contender, rebuilder, draft capital, and most active manager",
  "The complete waiver board — stash candidates, watchlist depth, and a FAAB shortlist",
  "Every Trade Hub idea, not just the first 2",
  "GM Targets watchlist up to 50 players (Free is capped at 3)",
  "Portfolio — your record, rank, and top need across every saved league, not just one",
];

/** Offline/error fallback only. Prices come from config/plan_prices.json via
 * the generated planPrices.generated.ts (the same file the edge function's
 * fallback and modules/stripe_billing.py use); the server's live Stripe Price
 * lookup is the source of truth whenever it's reachable. */
export const FALLBACK_PUBLIC_PLANS: BillingPlan[] = (["monthly", "annual"] as const).map((interval) => ({
  tier: "pro",
  interval,
  label: FALLBACK_PLAN_PRICES[interval].label,
  price: FALLBACK_PLAN_PRICES[interval].price,
  cadence: FALLBACK_PLAN_PRICES[interval].cadence,
  features: FALLBACK_FEATURES,
}));
