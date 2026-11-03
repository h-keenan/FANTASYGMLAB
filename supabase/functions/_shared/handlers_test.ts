import { assert, assertEquals } from "./assert.ts";
import { signStripePayload, verifyStripeSignature } from "./stripe_signature.ts";
import { handle as stripeWebhook } from "../stripe-webhook/handler.ts";
import { handle as rcWebhook } from "../revenuecat-webhook/handler.ts";
import { handle as checkout } from "../create-checkout-session/handler.ts";
import { handle as portal } from "../billing-portal-session/handler.ts";
import { launchWeekActive, priceIdForPlan, safeReturnPath, encodeForm } from "./stripe_api.ts";
import { parseTrialDays } from "./config.ts";
import { FALLBACK_PLAN_PRICES } from "./plan_prices.ts";
import {
  BASE_ENV, envOf, fakeFetch, j, stripeConfig, subscriptionEvent, USER_ID, WEBHOOK_SECRET, PRICE_PRO_MONTHLY, PRICE_PRO_ANNUAL, PRICE_LAUNCH,
} from "./fixtures.ts";

const NOW_S = 1_800_000_000;
const NOW = new Date(NOW_S * 1000);

// ---------- signature ----------
Deno.test("signature: valid header verifies and returns the event", async () => {
  const body = JSON.stringify({ id: "evt_1", type: "x" });
  const header = await signStripePayload(WEBHOOK_SECRET, body, NOW_S);
  const ev = await verifyStripeSignature(body, header, WEBHOOK_SECRET, { nowSeconds: NOW_S });
  assertEquals(ev.id, "evt_1");
});

Deno.test("signature: tampered body, wrong secret, stale timestamp, malformed header all rejected", async () => {
  const body = JSON.stringify({ id: "evt_1" });
  const header = await signStripePayload(WEBHOOK_SECRET, body, NOW_S);
  const cases: [string, string, string, number][] = [
    [body + " ", header, WEBHOOK_SECRET, NOW_S],
    [body, header, "whsec_other", NOW_S],
    [body, header, WEBHOOK_SECRET, NOW_S + 301],
    [body, "garbage", WEBHOOK_SECRET, NOW_S],
    [body, `t=${NOW_S}`, WEBHOOK_SECRET, NOW_S],
    [body, `v1=abc`, WEBHOOK_SECRET, NOW_S],
  ];
  for (const [b, h, s, now] of cases) {
    let threw = false;
    try {
      await verifyStripeSignature(b, h, s, { nowSeconds: now });
    } catch {
      threw = true;
    }
    assert(threw, `should reject: ${h.slice(0, 20)}`);
  }
});

Deno.test("signature: any one matching v1 among several is accepted (secret rotation)", async () => {
  const body = "{}";
  const good = await signStripePayload(WEBHOOK_SECRET, body, NOW_S);
  const header = `${good},v1=${"0".repeat(64)}`;
  await verifyStripeSignature(body, header, WEBHOOK_SECRET, { nowSeconds: NOW_S });
});

// ---------- stripe-webhook handler ----------
async function signedRequest(event: unknown, over: { secret?: string; header?: string | null } = {}) {
  const body = JSON.stringify(event);
  const headers: Record<string, string> = {};
  const header = over.header === undefined ? await signStripePayload(over.secret ?? WEBHOOK_SECRET, body, NOW_S) : over.header;
  if (header !== null) headers["stripe-signature"] = header;
  return new Request("https://x.test/stripe-webhook", { method: "POST", body, headers });
}

function webhookDeps(opts: { existingEvent?: boolean; patchStatus?: number } = {}) {
  const f = fakeFetch({
    "GET /rest/v1/billing_webhook_events": () => j(opts.existingEvent ? [{ event_id: "evt_1" }] : []),
    "POST /rest/v1/billing_webhook_events": () => new Response(null, { status: 201 }),
    "PATCH /rest/v1/profiles": () => (opts.patchStatus && opts.patchStatus >= 400 ? j({ message: "boom" }, opts.patchStatus) : new Response(null, { status: 204 })),
  });
  return { f, deps: { env: envOf(BASE_ENV), fetch: f.fn, now: () => NOW } };
}

Deno.test("stripe-webhook: 400 without Stripe-Signature, 400 on bad signature, no DB writes", async () => {
  const { f, deps } = webhookDeps();
  const ev = subscriptionEvent("customer.subscription.updated");
  assertEquals((await stripeWebhook(await signedRequest(ev, { header: null }), deps)).status, 400);
  assertEquals((await stripeWebhook(await signedRequest(ev, { secret: "whsec_wrong" }), deps)).status, 400);
  assertEquals(f.calls.length, 0);
});

Deno.test("stripe-webhook: GET not allowed", async () => {
  const { deps } = webhookDeps();
  assertEquals((await stripeWebhook(new Request("https://x.test/", { method: "GET" }), deps)).status, 405);
});

Deno.test("stripe-webhook: event mode must match billing mode", async () => {
  const { f, deps } = webhookDeps();
  const res = await stripeWebhook(await signedRequest(subscriptionEvent("customer.subscription.updated", {}, { livemode: true })), deps);
  assertEquals(res.status, 400);
  assertEquals(f.calls.length, 0);
});

Deno.test("stripe-webhook: valid active event PATCHes profile with service role + ordering guard, then logs event", async () => {
  const { f, deps } = webhookDeps();
  const res = await stripeWebhook(await signedRequest(subscriptionEvent("customer.subscription.updated")), deps);
  assertEquals(res.status, 200);
  const out = await res.json();
  assertEquals(out.received, true);
  assertEquals(out.entitlement, "premium");
  const patch = f.calls.find((c) => c.init.method === "PATCH")!;
  assert(patch.url.includes(`user_id=eq.${USER_ID}`));
  assert(decodeURIComponent(patch.url).includes("stripe_event_created_at.lt."));
  assertEquals((patch.init.headers as Record<string, string>).Authorization, "Bearer service-role-fixture");
  const body = JSON.parse(patch.init.body as string);
  assertEquals(body.entitlement, "premium");
  assert(f.calls.some((c) => c.init.method === "POST" && c.url.includes("billing_webhook_events")));
});

Deno.test("stripe-webhook: duplicate event id => 200 skipped, no PATCH", async () => {
  const { f, deps } = webhookDeps({ existingEvent: true });
  const res = await stripeWebhook(await signedRequest(subscriptionEvent("customer.subscription.updated")), deps);
  assertEquals(res.status, 200);
  assertEquals((await res.json()).skipped, true);
  assert(!f.calls.some((c) => c.init.method === "PATCH"));
});

Deno.test("stripe-webhook: DB failure => 500 so Stripe retries", async () => {
  const { deps } = webhookDeps({ patchStatus: 500 });
  const res = await stripeWebhook(await signedRequest(subscriptionEvent("customer.subscription.updated")), deps);
  assertEquals(res.status, 500);
});

Deno.test("stripe-webhook: trial_ends_at column missing => retried without it", async () => {
  let n = 0;
  const f = fakeFetch({
    "GET /rest/v1/billing_webhook_events": () => j([]),
    "POST /rest/v1/billing_webhook_events": () => new Response(null, { status: 201 }),
    "PATCH /rest/v1/profiles": (c) => {
      n++;
      if (n === 1) return j({ message: "column profiles.trial_ends_at does not exist" }, 400);
      assert(!("trial_ends_at" in JSON.parse(c.init.body as string)));
      return new Response(null, { status: 204 });
    },
  });
  const res = await stripeWebhook(await signedRequest(subscriptionEvent("customer.subscription.updated")), { env: envOf(BASE_ENV), fetch: f.fn, now: () => NOW });
  assertEquals(res.status, 200);
  assertEquals(n, 2);
});

Deno.test("stripe-webhook: live mode price allowlist blocks unknown price end-to-end", async () => {
  const { f, deps } = webhookDeps();
  const env = envOf({ ...BASE_ENV, STRIPE_BILLING_MODE: "live", STRIPE_SECRET_KEY: "sk_live_fixture" });
  const ev = subscriptionEvent("customer.subscription.updated", { items: { data: [{ price: { id: "price_evil" } }] } }, { livemode: true });
  const res = await stripeWebhook(await signedRequest(ev), { ...deps, env });
  assertEquals(res.status, 200);
  assertEquals((await res.json()).skipped, true);
  assert(!f.calls.some((c) => c.init.method === "PATCH"));
});

Deno.test("stripe-webhook: misconfigured secret => 500, never processes", async () => {
  const { f, deps } = webhookDeps();
  const res = await stripeWebhook(await signedRequest(subscriptionEvent("customer.subscription.updated")), { ...deps, env: envOf({ ...BASE_ENV, STRIPE_WEBHOOK_SECRET: "" }) });
  assertEquals(res.status, 500);
  assertEquals(f.calls.length, 0);
});

// ---------- revenuecat-webhook ----------
function rcRequest(event: unknown, auth: string | null = "rc-auth-fixture") {
  const headers: Record<string, string> = {};
  if (auth !== null) headers.authorization = auth;
  return new Request("https://x.test/revenuecat-webhook", { method: "POST", body: JSON.stringify({ event }), headers });
}
function rcDeps(activeKeys: string[], over: { rcStatus?: number; seen?: boolean } = {}) {
  const f = fakeFetch({
    "GET https://api.revenuecat.com": () =>
      over.rcStatus ? j({}, over.rcStatus) : j({ items: activeKeys.map((k) => ({ lookup_key: k })) }),
    "GET /rest/v1/billing_webhook_events": () => j(over.seen ? [{ event_id: "rc_1" }] : []),
    "POST /rest/v1/billing_webhook_events": () => new Response(null, { status: 201 }),
    "PATCH /rest/v1/profiles": () => new Response(null, { status: 204 }),
  });
  return { f, deps: { env: envOf(BASE_ENV), fetch: f.fn, now: () => NOW } };
}
const rcEvent = (over: Record<string, unknown> = {}) => ({
  id: "rc_1", type: "INITIAL_PURCHASE", app_user_id: USER_ID, environment: "SANDBOX", event_timestamp_ms: NOW_S * 1000, ...over,
});

Deno.test("revenuecat: missing header 400, wrong token 401, no writes", async () => {
  const { f, deps } = rcDeps(["premium"]);
  assertEquals((await rcWebhook(rcRequest(rcEvent(), null), deps)).status, 400);
  assertEquals((await rcWebhook(rcRequest(rcEvent(), "nope"), deps)).status, 401);
  assertEquals(f.calls.length, 0);
});

Deno.test("revenuecat: entitlement mapping from active lookup keys (front_office > premium > free)", async () => {
  for (const [keys, want] of [[["front_office", "premium"], "front_office"], [["premium"], "premium"], [[], "free"]] as const) {
    const { f, deps } = rcDeps([...keys]);
    const res = await rcWebhook(rcRequest(rcEvent()), deps);
    assertEquals(res.status, 200);
    assertEquals((await res.json()).entitlement, want);
    const body = JSON.parse(f.calls.find((c) => c.init.method === "PATCH")!.init.body as string);
    assertEquals(body.entitlement, want);
    assertEquals(body.revenuecat_app_user_id, USER_ID);
  }
});

Deno.test("revenuecat: custom lookup keys honoured", async () => {
  const f = fakeFetch({
    "GET https://api.revenuecat.com": () => j({ items: [{ lookup_key: "pro_custom" }] }),
    "GET /rest/v1/billing_webhook_events": () => j([]),
    "POST /rest/v1/billing_webhook_events": () => new Response(null, { status: 201 }),
    "PATCH /rest/v1/profiles": () => new Response(null, { status: 204 }),
  });
  const res = await rcWebhook(rcRequest(rcEvent()), { env: envOf({ ...BASE_ENV, REVENUECAT_ENTITLEMENT_LOOKUP_KEY: "pro_custom" }), fetch: f.fn, now: () => NOW });
  assertEquals((await res.json()).entitlement, "premium");
});

Deno.test("revenuecat: TEST event, wrong environment, missing user are skipped without RC/DB calls", async () => {
  for (const ev of [rcEvent({ type: "TEST" }), rcEvent({ environment: "PRODUCTION" }), rcEvent({ app_user_id: "" })]) {
    const { f, deps } = rcDeps(["premium"]);
    const res = await rcWebhook(rcRequest(ev), deps);
    assertEquals(res.status, 200);
    assertEquals((await res.json()).skipped, true);
    assert(!f.calls.some((c) => c.init.method === "PATCH" || c.url.includes("revenuecat.com")));
  }
});

Deno.test("revenuecat: duplicate event id skipped; RC 404 => free; anonymous id acknowledged", async () => {
  const dup = rcDeps(["premium"], { seen: true });
  const r1 = await rcWebhook(rcRequest(rcEvent()), dup.deps);
  assertEquals((await r1.json()).skipped, true);
  assert(!dup.f.calls.some((c) => c.init.method === "PATCH"));

  const nf = rcDeps([], { rcStatus: 404 });
  assertEquals((await (await rcWebhook(rcRequest(rcEvent()), nf.deps)).json()).entitlement, "free");

  const anon = rcDeps(["premium"]);
  const r3 = await rcWebhook(rcRequest(rcEvent({ app_user_id: "$RCAnonymousID:abc" })), anon.deps);
  assertEquals(r3.status, 200);
  assert(!anon.f.calls.some((c) => c.init.method === "PATCH"));
});

Deno.test("revenuecat: trial period sets trial_ends_at; non-trial clears it", async () => {
  const exp = NOW_S * 1000 + 3 * 86400_000;
  const a = rcDeps(["premium"]);
  await rcWebhook(rcRequest(rcEvent({ period_type: "TRIAL", expiration_at_ms: exp })), a.deps);
  const body = JSON.parse(a.f.calls.find((c) => c.init.method === "PATCH")!.init.body as string);
  assertEquals(body.trial_ends_at, new Date(exp).toISOString());
  const b = rcDeps(["premium"]);
  await rcWebhook(rcRequest(rcEvent({ type: "RENEWAL", period_type: "NORMAL", is_trial_conversion: true })), b.deps);
  const body2 = JSON.parse(b.f.calls.find((c) => c.init.method === "PATCH")!.init.body as string);
  assertEquals(body2.trial_ends_at, null);
  assert(decodeURIComponent(b.f.calls.find((c) => c.init.method === "PATCH")!.url).includes("revenuecat_event_created_at.lt."));
});

Deno.test("revenuecat: upstream RC failure => non-2xx so RevenueCat retries", async () => {
  const { deps } = rcDeps([], { rcStatus: 500 });
  assertEquals((await rcWebhook(rcRequest(rcEvent()), deps)).status, 502);
});

// ---------- checkout / portal ----------
function userRoutes(profile: Record<string, unknown> | null, email = "real@example.com", isAnonymous = false) {
  return {
    "GET /auth/v1/user": (c: { init: RequestInit }) => {
      const auth = (c.init.headers as Record<string, string>).Authorization;
      return auth === "Bearer good-jwt" ? j({ id: USER_ID, email, is_anonymous: isAnonymous }) : j({ msg: "bad" }, 401);
    },
    "GET /rest/v1/profiles": () => (profile === null ? j({ message: "boom" }, 500) : j([profile])),
  };
}
const checkoutReq = (body: unknown, jwt: string | null = "good-jwt") =>
  new Request("https://x.test/create-checkout-session", {
    method: "POST",
    body: JSON.stringify(body),
    headers: { ...(jwt ? { authorization: `Bearer ${jwt}` } : {}), origin: "https://app.example.test" },
  });
const stripeRoutes = (hadSub = false) => ({
  "GET https://api.stripe.com/v1/customers": () => j({ data: hadSub ? [{ id: "cus_old" }] : [] }),
  "GET https://api.stripe.com/v1/subscriptions": () => j({ data: [{ id: "sub_old" }] }),
  "POST https://api.stripe.com/v1/checkout/sessions": () => j({ id: "cs_1", client_secret: "cs_secret_1", url: "https://checkout.stripe.test/c" }),
});

function formOf(c: { init: RequestInit }) {
  return new URLSearchParams(String(c.init.body));
}

Deno.test("checkout: rejects missing/invalid JWT and never calls Stripe", async () => {
  const f = fakeFetch({ ...userRoutes({}), ...stripeRoutes() });
  const deps = { env: envOf(BASE_ENV), fetch: f.fn, now: () => NOW };
  assertEquals((await checkout(checkoutReq({}, null), deps)).status, 401);
  assertEquals((await checkout(checkoutReq({}, "bad-jwt"), deps)).status, 401);
  assert(!f.calls.some((c) => c.url.includes("api.stripe.com")));
});

Deno.test("checkout: anonymous (guest) user gets 403 account_required and no profile/Stripe call", async () => {
  const f = fakeFetch({ ...userRoutes({}, "", true), ...stripeRoutes() });
  const res = await checkout(checkoutReq({ tier: "pro" }), { env: envOf(BASE_ENV), fetch: f.fn, now: () => NOW });
  assertEquals(res.status, 403);
  const body = await res.json();
  assertEquals(body.ok, false);
  assertEquals(body.code, "account_required");
  assertEquals(body.error, "Create an account to start your free trial.");
  assert(!f.calls.some((c) => c.url.includes("api.stripe.com")));
  assert(!f.calls.some((c) => c.url.includes("/rest/v1/profiles")));
});

Deno.test("checkout: embedded session for new user: verified email prefill, trial from constant, return_url, metadata", async () => {
  const f = fakeFetch({ ...userRoutes({}), ...stripeRoutes() });
  const res = await checkout(checkoutReq({ tier: "pro", interval: "monthly", return_to: "/dashboard", email: "attacker@evil.test" }), { env: envOf(BASE_ENV), fetch: f.fn, now: () => NOW });
  assertEquals(res.status, 200);
  const out = await res.json();
  assertEquals(out.client_secret, "cs_secret_1");
  assertEquals(out.trial_days, 3);
  assertEquals(res.headers.get("access-control-allow-origin"), "https://app.example.test");
  const form = formOf(f.calls.find((c) => c.url.endsWith("/checkout/sessions"))!);
  assertEquals(form.get("customer_email"), "real@example.com");
  assertEquals(form.get("customer"), null);
  assertEquals(form.get("ui_mode"), "embedded");
  assertEquals(form.get("return_url"), "https://app.example.test/dashboard?billing=complete");
  assertEquals(form.get("success_url"), null);
  assertEquals(form.get("line_items[0][price]"), PRICE_PRO_MONTHLY);
  assertEquals(form.get("subscription_data[trial_period_days]"), "3");
  assertEquals(form.get("subscription_data[trial_settings][end_behavior][missing_payment_method]"), "cancel");
  assertEquals(form.get("client_reference_id"), USER_ID);
  assertEquals(form.get("metadata[supabase_user_id]"), USER_ID);
  assertEquals(form.get("subscription_data[metadata][supabase_user_id]"), USER_ID);
  assertEquals(form.get("payment_method_collection"), "always");
  const idem = (f.calls.find((c) => c.url.endsWith("/checkout/sessions"))!.init.headers as Record<string, string>)["Idempotency-Key"];
  assert(idem.startsWith(`fgl-checkout-${USER_ID}-monthly-${PRICE_PRO_MONTHLY}-embedded-t3`));
});

Deno.test("checkout: existing customer is reused (no customer_email) and gets no trial", async () => {
  const f = fakeFetch({ ...userRoutes({ stripe_customer_id: "cus_known" }), ...stripeRoutes() });
  const res = await checkout(checkoutReq({ interval: "annual" }), { env: envOf(BASE_ENV), fetch: f.fn, now: () => NOW });
  assertEquals(res.status, 200);
  const form = formOf(f.calls.find((c) => c.url.endsWith("/checkout/sessions"))!);
  assertEquals(form.get("customer"), "cus_known");
  assertEquals(form.get("customer_email"), null);
  assertEquals(form.get("subscription_data[trial_period_days]"), null);
  assertEquals(form.get("line_items[0][price]"), PRICE_PRO_ANNUAL);
});

Deno.test("checkout: trial forfeited when Stripe shows a prior subscription for the email, or profile unreadable (fail closed)", async () => {
  const prior = fakeFetch({ ...userRoutes({}), ...stripeRoutes(true) });
  await checkout(checkoutReq({}), { env: envOf(BASE_ENV), fetch: prior.fn, now: () => NOW });
  assertEquals(formOf(prior.calls.find((c) => c.url.endsWith("/checkout/sessions"))!).get("subscription_data[trial_period_days]"), null);
  const unreadable = fakeFetch({ ...userRoutes(null), ...stripeRoutes() });
  await checkout(checkoutReq({}), { env: envOf(BASE_ENV), fetch: unreadable.fn, now: () => NOW });
  assertEquals(formOf(unreadable.calls.find((c) => c.url.endsWith("/checkout/sessions"))!).get("subscription_data[trial_period_days]"), null);
});

Deno.test("checkout: Front Office never gets a trial; unknown tier/interval/missing price fail closed", async () => {
  const f = fakeFetch({ ...userRoutes({}), ...stripeRoutes() });
  const deps = { env: envOf(BASE_ENV), fetch: f.fn, now: () => NOW };
  assertEquals((await checkout(checkoutReq({ tier: "front_office", interval: "annual" }), deps)).status, 200);
  const form = formOf(f.calls.find((c) => c.url.endsWith("/checkout/sessions"))!);
  assertEquals(form.get("line_items[0][price]"), "price_front_office");
  assertEquals(form.get("subscription_data[trial_period_days]"), null);
  assertEquals((await checkout(checkoutReq({ tier: "gold" }), deps)).status, 503);
  assertEquals((await checkout(checkoutReq({ interval: "weekly" }), deps)).status, 503);
  const noFo = { ...deps, env: envOf({ ...BASE_ENV, STRIPE_PRICE_FRONT_OFFICE_ANNUAL: "" }) };
  assertEquals((await checkout(checkoutReq({ tier: "front_office" }), noFo)).status, 503);
});

Deno.test("checkout: hosted mode returns checkout_url with success/cancel urls", async () => {
  const f = fakeFetch({ ...userRoutes({}), ...stripeRoutes() });
  const res = await checkout(checkoutReq({ ui_mode: "hosted" }), { env: envOf(BASE_ENV), fetch: f.fn, now: () => NOW });
  assertEquals((await res.json()).checkout_url, "https://checkout.stripe.test/c");
  const form = formOf(f.calls.find((c) => c.url.endsWith("/checkout/sessions"))!);
  assertEquals(form.get("success_url"), "https://app.example.test/premium?billing=success");
  assertEquals(form.get("return_url"), null);
});

Deno.test("checkout: STRIPE_TRIAL_DAYS=0 disables trial; junk disables; unset => constant 3", () => {
  assertEquals(parseTrialDays("0"), 0);
  assertEquals(parseTrialDays("abc"), 0);
  assertEquals(parseTrialDays(""), 3);
  assertEquals(parseTrialDays(undefined), 3);
  assertEquals(parseTrialDays("500"), 90);
  assertEquals(parseTrialDays("-2"), 0);
});

Deno.test("price selection + launch week + return path safety + form encoding", () => {
  const cfg = stripeConfig();
  assertEquals(priceIdForPlan(cfg, "pro", "annual", new Date("2026-10-15T12:00:00Z")), PRICE_LAUNCH);
  assertEquals(priceIdForPlan(cfg, "pro", "annual", new Date("2026-10-20T12:00:00Z")), PRICE_PRO_ANNUAL);
  assertEquals(priceIdForPlan(cfg, "pro", "monthly", new Date("2026-10-15T12:00:00Z")), PRICE_PRO_MONTHLY);
  assertEquals(launchWeekActive(new Date("2026-10-19T04:00:00Z")), true);
  assertEquals(launchWeekActive(new Date("2026-10-19T06:00:00Z")), false);
  assertEquals(safeReturnPath("//evil.test"), "/premium");
  assertEquals(safeReturnPath("https://evil.test"), "/premium");
  assertEquals(safeReturnPath("/ok/path"), "/ok/path");
  assertEquals(encodeForm({ a: { b: [{ c: 1 }] }, d: undefined }), ["a%5Bb%5D%5B0%5D%5Bc%5D=1"]);
});

Deno.test("portal: customer id comes from the verified user's profile; 404 when none; 401 without JWT", async () => {
  const mk = (profile: Record<string, unknown>) =>
    fakeFetch({
      ...userRoutes(profile),
      "POST https://api.stripe.com/v1/billing_portal/sessions": () => j({ url: "https://billing.stripe.test/p" }),
    });
  const ok = mk({ stripe_customer_id: "cus_9" });
  const req = new Request("https://x.test/p", { method: "POST", headers: { authorization: "Bearer good-jwt" }, body: "{}" });
  const res = await portal(req, { env: envOf(BASE_ENV), fetch: ok.fn });
  assertEquals((await res.json()).portal_url, "https://billing.stripe.test/p");
  const form = formOf(ok.calls.find((c) => c.url.includes("billing_portal"))!);
  assertEquals(form.get("customer"), "cus_9");
  assertEquals(form.get("return_url"), "https://app.example.test/premium");

  const none = mk({});
  const r2 = await portal(new Request("https://x.test/p", { method: "POST", headers: { authorization: "Bearer good-jwt" } }), { env: envOf(BASE_ENV), fetch: none.fn });
  assertEquals(r2.status, 404);
  const r3 = await portal(new Request("https://x.test/p", { method: "POST" }), { env: envOf(BASE_ENV), fetch: none.fn });
  assertEquals(r3.status, 401);
});

// ---------- billing-plans ----------
import { handle as plans, formatPriceAmount, resetPriceCacheForTests, PREMIUM_FEATURE_LINES } from "../billing-plans/handler.ts";

const plansReq = (jwt: string | null = null, method = "GET") =>
  new Request("https://x.test/billing-plans", {
    method,
    headers: { origin: "https://app.example.test", ...(jwt ? { authorization: `Bearer ${jwt}` } : {}) },
  });
const priceRoutes = () => ({
  [`GET https://api.stripe.com/v1/prices/${PRICE_PRO_MONTHLY}`]: () => j({ unit_amount: 499, currency: "usd", recurring: { interval: "month" } }),
  [`GET https://api.stripe.com/v1/prices/${PRICE_PRO_ANNUAL}`]: () => j({ unit_amount: 2999, currency: "usd", recurring: { interval: "year" } }),
});

Deno.test("billing-plans: live Stripe prices, publishable key, trial days; anonymous works", async () => {
  resetPriceCacheForTests();
  const f = fakeFetch(priceRoutes());
  const res = await plans(plansReq(), { env: envOf({ ...BASE_ENV, STRIPE_PUBLISHABLE_KEY: "pk_test_abc" }), fetch: f.fn });
  assertEquals(res.status, 200);
  assertEquals(res.headers.get("access-control-allow-origin"), "https://app.example.test");
  const body = await res.json();
  assertEquals(body.ok, true);
  assertEquals(body.stripe_publishable_key, "pk_test_abc");
  assertEquals(body.trial, { days: 0, eligible: false });
  assertEquals(body.trial_days, 3);
  assertEquals(body.plans.length, 2);
  assertEquals(body.plans[0], { tier: "pro", interval: "monthly", label: "Monthly", price: "$4.99", cadence: "per month", features: PREMIUM_FEATURE_LINES });
  assertEquals(body.plans[1].price, "$29.99");
  assertEquals(body.plans[1].cadence, "per year");
  assert(f.calls.every((c) => (c.init.headers as Record<string, string>).Authorization === "Bearer sk_test_fixture"));
});

Deno.test("billing-plans: prices cached for 5 minutes, refreshed after", async () => {
  resetPriceCacheForTests();
  const f = fakeFetch(priceRoutes());
  let t = 1_800_000_000_000;
  const deps = { env: envOf(BASE_ENV), fetch: f.fn, now: () => new Date(t) };
  await plans(plansReq(), deps);
  await plans(plansReq(), deps);
  assertEquals(f.calls.length, 2); // 2 price reads; second request served from cache
  t += 301_000;
  await plans(plansReq(), deps);
  assertEquals(f.calls.length, 4);
});

Deno.test("billing-plans: Stripe failure or missing config falls back to defaults, never errors", async () => {
  resetPriceCacheForTests();
  const bad = fakeFetch({}); // every call unrouted -> 599
  const r1 = await plans(plansReq(), { env: envOf(BASE_ENV), fetch: bad.fn });
  const b1 = await r1.json();
  assertEquals(r1.status, 200);
  assertEquals(b1.plans.map((p: { price: string }) => p.price), [FALLBACK_PLAN_PRICES.monthly.price, FALLBACK_PLAN_PRICES.annual.price]);
  resetPriceCacheForTests();
  const none = fakeFetch({});
  const r2 = await plans(plansReq(), { env: envOf({ SUPABASE_URL: "https://proj.supabase.test" }), fetch: none.fn });
  assertEquals((await r2.json()).stripe_publishable_key, "");
  assertEquals(none.calls.length, 0);
});

Deno.test("billing-plans: price without a usable amount falls back to defaults", async () => {
  resetPriceCacheForTests();
  const f = fakeFetch({
    ...priceRoutes(),
    [`GET https://api.stripe.com/v1/prices/${PRICE_PRO_ANNUAL}`]: () => j({ unit_amount: null, currency: "usd" }),
  });
  const body = await (await plans(plansReq(), { env: envOf(BASE_ENV), fetch: f.fn })).json();
  assertEquals(body.plans.map((p: { price: string }) => p.price), [FALLBACK_PLAN_PRICES.monthly.price, FALLBACK_PLAN_PRICES.annual.price]);
});

Deno.test("billing-plans: signed-in account with no billing history is trial-eligible; with history is not", async () => {
  resetPriceCacheForTests();
  const mk = (profile: Record<string, unknown> | null) => fakeFetch({ ...priceRoutes(), ...userRoutes(profile) });
  const fresh = await (await plans(plansReq("good-jwt"), { env: envOf(BASE_ENV), fetch: mk({}).fn })).json();
  assertEquals(fresh.trial, { days: 3, eligible: true });
  const used = await (await plans(plansReq("good-jwt"), { env: envOf(BASE_ENV), fetch: mk({ trial_ends_at: "2026-01-01" }).fn })).json();
  assertEquals(used.trial, { days: 0, eligible: false });
  const unreadable = await (await plans(plansReq("good-jwt"), { env: envOf(BASE_ENV), fetch: mk(null).fn })).json();
  assertEquals(unreadable.trial, { days: 0, eligible: false });
  // no Stripe customer-by-email lookup (FastAPI check_stripe=False)
  const f = mk({});
  await plans(plansReq("good-jwt"), { env: envOf(BASE_ENV), fetch: f.fn });
  assert(!f.calls.some((c) => c.url.includes("/customers")));
});

Deno.test("billing-plans: anonymous (guest) user with a valid JWT gets no trial", async () => {
  resetPriceCacheForTests();
  const f = fakeFetch({ ...priceRoutes(), ...userRoutes({}, "", true) });
  const r = await plans(plansReq("good-jwt"), { env: envOf(BASE_ENV), fetch: f.fn });
  assertEquals(r.status, 200);
  const body = await r.json();
  assertEquals(body.trial, { days: 0, eligible: false });
  assertEquals(body.trial_days, 3);
  assert(!f.calls.some((c) => c.url.includes("/rest/v1/profiles")));
});

Deno.test("billing-plans: invalid JWT or anon key is anonymous; trial disabled => 0 days", async () => {
  resetPriceCacheForTests();
  const f = fakeFetch({ ...priceRoutes(), ...userRoutes({}) });
  const r = await plans(plansReq("anon-fixture"), { env: envOf(BASE_ENV), fetch: f.fn });
  assertEquals(r.status, 200);
  assertEquals((await r.json()).trial.eligible, false);
  const off = await (await plans(plansReq("good-jwt"), { env: envOf({ ...BASE_ENV, STRIPE_TRIAL_DAYS: "0" }), fetch: f.fn })).json();
  assertEquals(off.trial, { days: 0, eligible: false });
  assertEquals(off.trial_days, 0);
});

Deno.test("billing-plans: OPTIONS preflight allows GET; POST rejected; amount formatting", async () => {
  const f = fakeFetch({});
  const pre = await plans(plansReq(null, "OPTIONS"), { env: envOf(BASE_ENV), fetch: f.fn });
  assertEquals(pre.status, 204);
  assert((pre.headers.get("access-control-allow-methods") ?? "").includes("GET"));
  assertEquals((await plans(plansReq(null, "POST"), { env: envOf(BASE_ENV), fetch: f.fn })).status, 405);
  assertEquals(formatPriceAmount(399, "usd"), "$3.99");
  assertEquals(formatPriceAmount(123456, ""), "$1,234.56");
  assertEquals(formatPriceAmount(399, "eur"), "EUR 3.99");
  assertEquals(formatPriceAmount(null, "usd"), "");
});

Deno.test("stripe-webhook: user with no profile row (guest account) gets the row created, not a silent no-op", async () => {
  const f = fakeFetch({
    "GET /rest/v1/billing_webhook_events": () => j([]),
    "POST /rest/v1/billing_webhook_events": () => new Response(null, { status: 201 }),
    "PATCH /rest/v1/profiles": () => j([]),
    "GET /rest/v1/profiles": () => j([]),
    "POST /rest/v1/profiles": () => new Response(null, { status: 201 }),
  });
  const deps = { env: envOf(BASE_ENV), fetch: f.fn, now: () => NOW };
  const res = await stripeWebhook(await signedRequest(subscriptionEvent("customer.subscription.created")), deps);
  assertEquals(res.status, 200);
  const ins = f.calls.find((c) => c.init.method === "POST" && c.url.includes("/rest/v1/profiles"))!;
  assert(ins !== undefined, "profile row must be created");
  const body = JSON.parse(ins.init.body as string);
  assertEquals(body.user_id, USER_ID);
  assertEquals(body.entitlement, "premium");
});

Deno.test("stripe-webhook: PATCH matching zero rows because of the ordering guard does not create a row", async () => {
  const f = fakeFetch({
    "GET /rest/v1/billing_webhook_events": () => j([]),
    "POST /rest/v1/billing_webhook_events": () => new Response(null, { status: 201 }),
    "PATCH /rest/v1/profiles": () => j([]),
    "GET /rest/v1/profiles": () => j([{ user_id: USER_ID }]),
  });
  const deps = { env: envOf(BASE_ENV), fetch: f.fn, now: () => NOW };
  const res = await stripeWebhook(await signedRequest(subscriptionEvent("customer.subscription.updated")), deps);
  assertEquals(res.status, 200);
  assert(!f.calls.some((c) => c.init.method === "POST" && c.url.includes("/rest/v1/profiles")));
});

Deno.test("stripe-webhook: profile create retries without trial_ends_at on an older schema", async () => {
  let posts = 0;
  const f = fakeFetch({
    "GET /rest/v1/billing_webhook_events": () => j([]),
    "POST /rest/v1/billing_webhook_events": () => new Response(null, { status: 201 }),
    "PATCH /rest/v1/profiles": () => j([]),
    "GET /rest/v1/profiles": () => j([]),
    "POST /rest/v1/profiles": (c) => {
      posts++;
      return "trial_ends_at" in JSON.parse(c.init.body as string)
        ? j({ message: "column profiles.trial_ends_at does not exist" }, 400)
        : new Response(null, { status: 201 });
    },
  });
  const deps = { env: envOf(BASE_ENV), fetch: f.fn, now: () => NOW };
  const res = await stripeWebhook(await signedRequest(subscriptionEvent("customer.subscription.created")), deps);
  assertEquals(res.status, 200);
  assertEquals(posts, 2);
});

// ---------- delete-account: cancel Stripe first, then delete ----------
import { handle as deleteAccount } from "../delete-account/handler.ts";

const delReq = (jwt: string | null = "good-jwt") =>
  new Request("https://x.test/delete-account", {
    method: "POST",
    headers: { ...(jwt ? { authorization: `Bearer ${jwt}` } : {}), origin: "https://app.example.test" },
    body: "{}",
  });
const SUBS = "https://api.stripe.com/v1/subscriptions";
function delRoutes(profile: Record<string, unknown>, over: Record<string, () => Response> = {}) {
  return {
    ...userRoutes(profile),
    [`GET ${SUBS}?customer=cus_1`]: () => j({ data: [{ id: "sub_1", status: "active" }, { id: "sub_old", status: "canceled" }] }),
    [`GET ${SUBS}/sub_1`]: () => j({ id: "sub_1", status: "active" }),
    [`DELETE ${SUBS}/sub_1`]: () => j({ id: "sub_1", status: "canceled" }),
    "POST /rest/v1/rpc/delete_user": () => new Response(null, { status: 204 }),
    ...over,
  };
}

Deno.test("delete-account: cancels the live Stripe subscription, then deletes with the caller's JWT", async () => {
  const f = fakeFetch(delRoutes({ stripe_customer_id: "cus_1", stripe_subscription_id: "sub_1" }));
  const res = await deleteAccount(delReq(), { env: envOf(BASE_ENV), fetch: f.fn });
  assertEquals(res.status, 200);
  const body = await res.json();
  assertEquals(body.ok, true);
  assertEquals(body.canceled_subscriptions, 1);
  const urls = f.calls.map((c) => `${c.init.method ?? "GET"} ${c.url}`);
  const del = urls.findIndex((u) => u === `DELETE ${SUBS}/sub_1`);
  const rpc = urls.findIndex((u) => u.includes("/rest/v1/rpc/delete_user"));
  assert(del >= 0 && rpc > del, "cancel must happen before the account delete");
  assertEquals(urls.filter((u) => u.startsWith("DELETE")).length, 1); // the canceled sub_old is not touched
  const rpcCall = f.calls[rpc];
  assertEquals((rpcCall.init.headers as Record<string, string>).Authorization, "Bearer good-jwt");
  assertEquals((f.calls[del].init.headers as Record<string, string>)["Idempotency-Key"], "delete-account-cancel-sub_1");
});

Deno.test("delete-account: a failed Stripe cancel blocks the delete and surfaces an error", async () => {
  const f = fakeFetch(delRoutes(
    { stripe_customer_id: "cus_1", stripe_subscription_id: "sub_1" },
    { [`DELETE ${SUBS}/sub_1`]: () => j({ error: { type: "api_error" } }, 500) },
  ));
  const res = await deleteAccount(delReq(), { env: envOf(BASE_ENV), fetch: f.fn });
  assertEquals(res.status, 502);
  assertEquals((await res.json()).code, "cancel_failed");
  assert(!f.calls.some((c) => c.url.includes("/rpc/delete_user")), "must not delete the account");
});

Deno.test("delete-account: Stripe unreachable or unconfigured with a customer on file never deletes", async () => {
  const down = fakeFetch(delRoutes({ stripe_customer_id: "cus_1" }, { [`GET ${SUBS}?customer=cus_1`]: () => j({}, 503) }));
  const r1 = await deleteAccount(delReq(), { env: envOf(BASE_ENV), fetch: down.fn });
  assertEquals(r1.status, 502);
  assert(!down.calls.some((c) => c.url.includes("/rpc/delete_user")));
  const noKey = fakeFetch(delRoutes({ stripe_customer_id: "cus_1" }));
  const r2 = await deleteAccount(delReq(), { env: envOf({ ...BASE_ENV, STRIPE_SECRET_KEY: "" }), fetch: noKey.fn });
  assertEquals(r2.status, 502);
  assert(!noKey.calls.some((c) => c.url.includes("/rpc/delete_user")));
});

Deno.test("delete-account: idempotent re-run (subscription already gone) still deletes; no billing needs no Stripe", async () => {
  const gone = fakeFetch(delRoutes(
    { stripe_customer_id: "cus_1", stripe_subscription_id: "sub_1" },
    { [`GET ${SUBS}?customer=cus_1`]: () => j({ data: [] }), [`GET ${SUBS}/sub_1`]: () => j({ error: { code: "resource_missing" } }, 404) },
  ));
  const r1 = await deleteAccount(delReq(), { env: envOf(BASE_ENV), fetch: gone.fn });
  assertEquals(r1.status, 200);
  assertEquals((await r1.json()).canceled_subscriptions, 0);
  assert(!gone.calls.some((c) => c.init.method === "DELETE" && c.url.includes("stripe")));

  const free = fakeFetch(delRoutes({}));
  const r2 = await deleteAccount(delReq(), { env: envOf(BASE_ENV), fetch: free.fn });
  assertEquals(r2.status, 200);
  assert(!free.calls.some((c) => c.url.includes("api.stripe.com")));
});

Deno.test("delete-account: unreadable billing profile blocks; RevenueCat user is flagged; bad JWT is 401", async () => {
  const unreadable = fakeFetch(delRoutes({}, { "GET /rest/v1/profiles": () => j({ message: "boom" }, 500) }));
  const r1 = await deleteAccount(delReq(), { env: envOf(BASE_ENV), fetch: unreadable.fn });
  assertEquals(r1.status, 502);
  assert(!unreadable.calls.some((c) => c.url.includes("/rpc/delete_user")));

  const rc = fakeFetch(delRoutes({ revenuecat_app_user_id: USER_ID }));
  const r2 = await deleteAccount(delReq(), { env: envOf(BASE_ENV), fetch: rc.fn });
  assertEquals((await r2.json()).store_subscription, true);

  const anon = fakeFetch({});
  const r3 = await deleteAccount(delReq(null), { env: envOf(BASE_ENV), fetch: anon.fn });
  assertEquals(r3.status, 401);
  assertEquals(anon.calls.length, 0);
});

Deno.test("delete-account: RPC failure after cancel reports an error (retry is safe)", async () => {
  const f = fakeFetch(delRoutes(
    { stripe_customer_id: "cus_1", stripe_subscription_id: "sub_1" },
    { "POST /rest/v1/rpc/delete_user": () => j({ message: "x" }, 500) },
  ));
  const res = await deleteAccount(delReq(), { env: envOf(BASE_ENV), fetch: f.fn });
  assertEquals(res.status, 502);
  assertEquals((await res.json()).code, "delete_failed");
});
