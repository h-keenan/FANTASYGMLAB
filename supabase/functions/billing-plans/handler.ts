// GET /billing-plans  (port of GET /v1/billing/plans in services/mobile_api_service.py)
// Public: works without a session (landing page). If a valid user JWT is sent,
// trial eligibility is computed for that account (cheap profile check only,
// same as FastAPI: check_stripe=False); otherwise the trial is reported as not
// eligible and `trial_days` still carries the offer length for marketing copy.
// Response shape is identical to FastAPI, plus one extra field: `trial_days`.

import {
  ANNUAL,
  loadStripeConfig,
  loadSupabaseConfig,
  MONTHLY,
  secretModeConfigured,
  StripeConfig,
  TIER_PRO,
} from "../_shared/config.ts";
import { corsHeaders, Deps } from "../_shared/deps.ts";
import { stripeRequest, trialEligible } from "../_shared/stripe_api.ts";
import { fetchBillingProfile, FetchFn, verifyUserJwt } from "../_shared/supabase_rest.ts";
import { errorResponse, isObj, Json, jsonResponse, pyInt, st } from "../_shared/util.ts";

type PlanDetail = [label: string, price: string, cadence: string];

/** Fallback display values (modules/stripe_billing.py DEFAULT_PLAN_DETAILS). */
export const DEFAULT_PLAN_DETAILS: Record<string, PlanDetail> = {
  [MONTHLY]: ["Monthly", "$3.99", "per month"],
  [ANNUAL]: ["Annual", "$19.99", "per year"],
};

/** Plans offered to new signups (Front Office is intentionally not listed, as in FastAPI). */
export const BILLING_PLAN_KEYS: [detailKey: string, tier: string, interval: string][] = [
  [MONTHLY, TIER_PRO, MONTHLY],
  [ANNUAL, TIER_PRO, ANNUAL],
];

/** modules/premium_benefits.py MOBILE_PREMIUM_BENEFIT_LINES (the `line` values), verbatim. */
export const PREMIUM_FEATURE_LINES: string[] = [
  "Your full Next Move briefing, not just the top 4",
  "League Pulse leaders in the mobile app — the league’s top contender, rebuilder, draft capital, and most active manager",
  "The complete waiver board — stash candidates, watchlist depth, and a FAAB shortlist",
  "Every Trade Hub idea, not just the first 2",
  "GM Targets watchlist up to 50 players (Free is capped at 3)",
  "Portfolio — your record, rank, and top need across every saved league, not just one",
];

/** Port of `_format_price_amount`: "$3.99", "EUR 3.99"; "" when unusable. */
export function formatPriceAmount(unitAmount: unknown, currency: string): string {
  const n = pyInt(unitAmount);
  if (n === null) return "";
  const code = st(currency).toUpperCase() || "USD";
  const symbol = code === "USD" ? "$" : `${code} `;
  const amount = (n / 100).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return `${symbol}${amount}`;
}

function priceDisplay(label: string, price: Json, fallbackCadence: string): PlanDetail {
  const text = formatPriceAmount(price.unit_amount, st(price.currency));
  if (!text) throw new Error("Stripe price is missing a usable unit amount.");
  const interval = isObj(price.recurring) ? st(price.recurring.interval) : "";
  return [label, text, interval ? `per ${interval}` : fallbackCadence];
}

const CACHE_TTL_MS = 5 * 60 * 1000;
const priceCache = new Map<string, { at: number; details: Record<string, PlanDetail> }>();
export function resetPriceCacheForTests() {
  priceCache.clear();
}

/** Real Stripe Price objects, briefly cached per isolate; null (never throws) on any failure. */
async function fetchLivePlanDetails(
  config: StripeConfig,
  fetchFn: FetchFn,
  nowMs: number,
): Promise<Record<string, PlanDetail> | null> {
  if (!secretModeConfigured(config) || !config.priceMonthly || !config.priceAnnual) return null;
  const key = `${config.billingMode}:${config.priceMonthly}:${config.priceAnnual}`;
  const hit = priceCache.get(key);
  if (hit && nowMs - hit.at < CACHE_TTL_MS) return hit.details;
  try {
    const monthly = await stripeRequest(fetchFn, config.secretKey, "GET", `/prices/${encodeURIComponent(config.priceMonthly)}`);
    const annual = await stripeRequest(fetchFn, config.secretKey, "GET", `/prices/${encodeURIComponent(config.priceAnnual)}`);
    const details = {
      [MONTHLY]: priceDisplay("Monthly", monthly, "per month"),
      [ANNUAL]: priceDisplay("Annual", annual, "per year"),
    };
    priceCache.set(key, { at: nowMs, details });
    return details;
  } catch {
    return null;
  }
}

export async function handle(req: Request, deps: Deps): Promise<Response> {
  const cors = corsHeaders(deps.env, req.headers.get("origin"));
  if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: cors });
  if (req.method !== "GET") return errorResponse(405, "Method not allowed.", cors);

  const config = loadStripeConfig(deps.env);
  const supabase = loadSupabaseConfig(deps.env);
  const nowMs = (deps.now ?? (() => new Date()))().getTime();

  const details = (await fetchLivePlanDetails(config, deps.fetch, nowMs)) ?? { ...DEFAULT_PLAN_DETAILS };
  const plans = BILLING_PLAN_KEYS.map(([detailKey, tier, interval]) => {
    const [label, price, cadence] = details[detailKey] ?? DEFAULT_PLAN_DETAILS[detailKey];
    return { tier, interval, label, price, cadence, features: PREMIUM_FEATURE_LINES };
  });

  // Per-account trial eligibility only when a valid user JWT came with the request.
  let eligible = false;
  const auth = req.headers.get("authorization") ?? "";
  if (auth && supabase.url && supabase.serviceRoleKey) {
    try {
      const user = await verifyUserJwt(supabase, deps.fetch, auth);
      const profile = await fetchBillingProfile(supabase, deps.fetch, user.id);
      // check-Stripe-by-email is skipped (email ""), exactly like FastAPI's check_stripe=False.
      eligible = await trialEligible(config, deps.fetch, {
        tier: TIER_PRO,
        email: "",
        profile,
        profileReadable: profile !== null,
      });
    } catch {
      eligible = false; // anon key / expired token / lookup failure => anonymous view
    }
  }

  return jsonResponse(
    {
      ok: true,
      plans,
      stripe_publishable_key: config.publishableKey,
      trial: { days: eligible ? config.trialDays : 0, eligible },
      // Extra (not in FastAPI): the offer length, for pages with no session.
      trial_days: config.trialDays,
    },
    200,
    { ...cors, "Cache-Control": auth ? "private, no-store" : "public, max-age=60" },
  );
}
