// Config loading. Every value comes from Supabase function secrets (env);
// nothing is hard-coded except the non-secret product constants below.
// Port of modules/stripe_billing.py (StripeBillingConfig / load_stripe_config)
// and modules/revenuecat_billing.py (RevenueCatBillingConfig).

import { Env, envValue, st } from "./util.ts";

/** THE single trial-length constant. GM Pro trial (both intervals), in days.
 *  STRIPE_TRIAL_DAYS (optional secret) can override it; 0 disables the trial. */
export const TRIAL_DAYS = 3;

export const MONTHLY = "monthly";
export const ANNUAL = "annual";
export const TIER_PRO = "pro";
export const TIER_FRONT_OFFICE = "front_office";

/** Wire values stored in profiles.entitlement ("premium" is the legacy name for Pro). */
export const SUPPORTED_ENTITLEMENT_VALUES = new Set(["free", "premium", "front_office"]);

export const DEFAULT_APP_BASE_URL = "https://app.fantasygmlab.com";

export function parseTrialDays(raw: unknown): number {
  const text = st(raw);
  if (!text) return TRIAL_DAYS;
  if (!/^[+-]?\d+$/.test(text)) return 0; // junk -> fail closed (no trial)
  return Math.max(0, Math.min(Number(text), 90));
}

export interface StripeConfig {
  billingMode: string;
  secretKey: string;
  /** Intentionally public; served to the browser by billing-plans. */
  publishableKey: string;
  webhookSecret: string;
  priceMonthly: string;
  priceAnnual: string;
  priceProAnnualLaunchWeek: string;
  priceFrontOfficeAnnual: string;
  appBaseUrl: string;
  trialDays: number;
}

export function loadStripeConfig(env: Env): StripeConfig {
  const v = (k: string) => envValue(env, k);
  return {
    billingMode: v("STRIPE_BILLING_MODE").toLowerCase() || "test",
    secretKey: v("STRIPE_SECRET_KEY"),
    publishableKey: v("STRIPE_PUBLISHABLE_KEY"),
    webhookSecret: v("STRIPE_WEBHOOK_SECRET"),
    // PRO_* canonical, legacy MONTHLY/ANNUAL fallback (same as Python).
    priceMonthly: v("STRIPE_PRICE_PRO_MONTHLY") || v("STRIPE_PRICE_MONTHLY"),
    priceAnnual: v("STRIPE_PRICE_PRO_ANNUAL") || v("STRIPE_PRICE_ANNUAL"),
    priceProAnnualLaunchWeek: v("STRIPE_PRICE_PRO_ANNUAL_LAUNCH_WEEK"),
    priceFrontOfficeAnnual: v("STRIPE_PRICE_FRONT_OFFICE_ANNUAL"),
    appBaseUrl: (v("APP_BASE_URL") || DEFAULT_APP_BASE_URL).replace(/\/+$/, ""),
    trialDays: parseTrialDays(env("STRIPE_TRIAL_DAYS")),
  };
}

export function secretModeConfigured(c: StripeConfig): boolean {
  return (c.billingMode === "test" || c.billingMode === "live") &&
    c.secretKey.startsWith(`sk_${c.billingMode}_`);
}
export function stripeConfigured(c: StripeConfig): boolean {
  return secretModeConfigured(c) && !!c.priceMonthly && !!c.priceAnnual;
}
export function webhookConfigured(c: StripeConfig): boolean {
  return !!c.webhookSecret && c.webhookSecret.startsWith("whsec_");
}

export interface RevenueCatConfig {
  billingMode: string;
  secretKey: string;
  projectId: string;
  webhookAuthToken: string;
  entitlementLookupKey: string;
  frontOfficeEntitlementLookupKey: string;
}

export function loadRevenueCatConfig(env: Env): RevenueCatConfig {
  const v = (k: string) => envValue(env, k);
  return {
    billingMode: v("REVENUECAT_BILLING_MODE").toLowerCase() || "test",
    secretKey: v("REVENUECAT_SECRET_KEY"),
    projectId: v("REVENUECAT_PROJECT_ID"),
    webhookAuthToken: v("REVENUECAT_WEBHOOK_AUTH_TOKEN"),
    entitlementLookupKey: v("REVENUECAT_ENTITLEMENT_LOOKUP_KEY") || "premium",
    frontOfficeEntitlementLookupKey: v("REVENUECAT_FRONT_OFFICE_ENTITLEMENT_LOOKUP_KEY") || "front_office",
  };
}
export const rcApiConfigured = (c: RevenueCatConfig) => !!c.secretKey && !!c.projectId;
export const rcExpectedEnvironment = (c: RevenueCatConfig) => (c.billingMode === "live" ? "PRODUCTION" : "SANDBOX");

export interface SupabaseConfig {
  url: string;
  serviceRoleKey: string;
  anonKey: string;
}
/** SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY / SUPABASE_ANON_KEY are injected by the platform. */
export function loadSupabaseConfig(env: Env): SupabaseConfig {
  return {
    url: envValue(env, "SUPABASE_URL").replace(/\/+$/, ""),
    serviceRoleKey: envValue(env, "SUPABASE_SERVICE_ROLE_KEY"),
    anonKey: envValue(env, "SUPABASE_ANON_KEY"),
  };
}
