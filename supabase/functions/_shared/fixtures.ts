// Test fixtures + fakes. Not imported by any deployed function.
import { StripeConfig } from "./config.ts";
import { BillingStore, ProfilePayload } from "./stripe_events.ts";
import { Json } from "./util.ts";

export const USER_ID = "11111111-2222-4333-8444-555555555555";
export const PRICE_PRO_MONTHLY = "price_pro_monthly";
export const PRICE_PRO_ANNUAL = "price_pro_annual";
export const PRICE_LAUNCH = "price_launch_week";
export const PRICE_FO = "price_front_office";
export const WEBHOOK_SECRET = "whsec_test_fixture_secret";

export function stripeConfig(over: Partial<StripeConfig> = {}): StripeConfig {
  return {
    billingMode: "test",
    secretKey: "sk_test_fixture",
    webhookSecret: WEBHOOK_SECRET,
    priceMonthly: PRICE_PRO_MONTHLY,
    priceAnnual: PRICE_PRO_ANNUAL,
    priceProAnnualLaunchWeek: PRICE_LAUNCH,
    priceFrontOfficeAnnual: PRICE_FO,
    appBaseUrl: "https://app.example.test",
    trialDays: 3,
    ...over,
  };
}

export function subscriptionEvent(
  type: string,
  sub: Json = {},
  extra: Json = {},
  data: Json = {},
): Json {
  return {
    id: "evt_1",
    type,
    created: 1_800_000_000,
    livemode: false,
    data: {
      object: {
        id: "sub_1",
        status: "active",
        customer: "cus_1",
        metadata: { supabase_user_id: USER_ID },
        items: { data: [{ price: { id: PRICE_PRO_MONTHLY } }] },
        ...sub,
      },
      ...data,
    },
    ...extra,
  };
}

/** In-memory BillingStore; mimics the ordering guard loosely by recording calls. */
export class FakeStore implements BillingStore {
  seen = new Set<string>();
  recorded: Json[] = [];
  updates: { userId: string; payload: ProfilePayload; ordering: Record<string, string> }[] = [];
  failUpdate = "";
  eventSeen(provider: string, eventId: string) {
    return Promise.resolve(this.seen.has(`${provider}:${eventId}`));
  }
  recordEvent(row: Json) {
    this.seen.add(`${row.provider}:${row.event_id}`);
    this.recorded.push(row);
    return Promise.resolve();
  }
  updateProfile(userId: string, payload: ProfilePayload, ordering: Record<string, string>) {
    if (this.failUpdate) return Promise.resolve({ ok: false, error: this.failUpdate });
    this.updates.push({ userId, payload, ordering });
    return Promise.resolve({ ok: true, error: "" });
  }
}

export interface Call {
  url: string;
  init: RequestInit;
}
/** Routes fetch by "METHOD url-substring"; records all calls. */
export function fakeFetch(routes: Record<string, (c: Call) => Response | Promise<Response>>) {
  const calls: Call[] = [];
  const fn = async (url: string, init: RequestInit = {}): Promise<Response> => {
    const call = { url, init };
    calls.push(call);
    const method = (init.method ?? "GET").toUpperCase();
    for (const [key, handler] of Object.entries(routes)) {
      const [m, ...rest] = key.split(" ");
      if (m === method && url.includes(rest.join(" "))) return await handler(call);
    }
    return new Response(JSON.stringify({ message: `unrouted ${method} ${url}` }), { status: 599 });
  };
  return { fn, calls };
}

export const j = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

export function envOf(map: Record<string, string>) {
  return (k: string) => map[k];
}

export const BASE_ENV = {
  SUPABASE_URL: "https://proj.supabase.test",
  SUPABASE_SERVICE_ROLE_KEY: "service-role-fixture",
  SUPABASE_ANON_KEY: "anon-fixture",
  STRIPE_BILLING_MODE: "test",
  STRIPE_SECRET_KEY: "sk_test_fixture",
  STRIPE_WEBHOOK_SECRET: WEBHOOK_SECRET,
  STRIPE_PRICE_PRO_MONTHLY: PRICE_PRO_MONTHLY,
  STRIPE_PRICE_PRO_ANNUAL: PRICE_PRO_ANNUAL,
  STRIPE_PRICE_PRO_ANNUAL_LAUNCH_WEEK: PRICE_LAUNCH,
  STRIPE_PRICE_FRONT_OFFICE_ANNUAL: PRICE_FO,
  APP_BASE_URL: "https://app.example.test",
  REVENUECAT_BILLING_MODE: "test",
  REVENUECAT_SECRET_KEY: "rc_secret_fixture",
  REVENUECAT_PROJECT_ID: "proj_fixture",
  REVENUECAT_WEBHOOK_AUTH_TOKEN: "rc-auth-fixture",
};
