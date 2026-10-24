import { assert, assertEquals } from "./assert.ts";
import {
  allowedPriceIds,
  buildProfileEntitlementPayload,
  durableEventOrderingParams,
  mapStripeEventToEntitlement,
  processStripeEvent,
} from "./stripe_events.ts";
import { FakeStore, PRICE_FO, PRICE_PRO_ANNUAL, PRICE_PRO_MONTHLY, stripeConfig, subscriptionEvent, USER_ID } from "./fixtures.ts";

const NOW = new Date(1_800_000_000 * 1000);
const map = (e: Record<string, unknown>, cfg = stripeConfig()) => mapStripeEventToEntitlement(e, { config: cfg, now: NOW });

Deno.test("active subscription -> premium (Pro stored as 'premium')", () => {
  for (const type of ["customer.subscription.created", "customer.subscription.updated", "checkout.session.completed"]) {
    assertEquals(map(subscriptionEvent(type)).entitlement, "premium", type);
  }
  assertEquals(map(subscriptionEvent("customer.subscription.updated")).user_id, USER_ID);
});

Deno.test("Front Office price -> front_office; unknown price still premium", () => {
  const fo = subscriptionEvent("customer.subscription.updated", { items: { data: [{ price: { id: PRICE_FO } }] } });
  assertEquals(map(fo).entitlement, "front_office");
  const other = subscriptionEvent("customer.subscription.updated", { items: { data: [{ price: { id: "price_unknown" } }] } });
  assertEquals(map(other).entitlement, "premium");
});

Deno.test("trialing stores as Pro and surfaces trial end; transition started", () => {
  const trialEnd = 1_800_000_000 + 3 * 86400;
  const a = map(subscriptionEvent("customer.subscription.created", { status: "trialing", trial_end: trialEnd }));
  assertEquals(a.entitlement, "premium");
  assertEquals(a.stripe_trial_end, new Date(trialEnd * 1000).toISOString());
  assertEquals(a.trial_transition, "started");
});

Deno.test("stale trialing event with past trial_end never grants", () => {
  const a = map(subscriptionEvent("customer.subscription.updated", { status: "trialing", trial_end: 1_700_000_000 }));
  assertEquals(a.entitlement, "free");
  assertEquals(a.reason, "customer.subscription.updated:trial_expired");
  assertEquals(a.stripe_trial_end, "");
});

Deno.test("trial converts: trialing -> active", () => {
  const e = subscriptionEvent("customer.subscription.updated", { status: "active" }, {}, { previous_attributes: { status: "trialing" } });
  const a = map(e);
  assertEquals(a.entitlement, "premium");
  assertEquals(a.trial_transition, "converted");
});

Deno.test("end of trial unpaid: trialing -> past_due/unpaid/canceled => free", () => {
  for (const status of ["past_due", "unpaid", "canceled", "incomplete_expired"]) {
    const e = subscriptionEvent("customer.subscription.updated", { status }, {}, { previous_attributes: { status: "trialing" } });
    const a = map(e);
    assertEquals(a.entitlement, "free", status);
    assertEquals(a.trial_transition, "canceled", status);
  }
  const pd = map(subscriptionEvent("customer.subscription.updated", { status: "past_due" }, {}, { previous_attributes: { status: "trialing" } }));
  assertEquals(pd.reason, "customer.subscription.updated:trial_ended_unpaid");
});

Deno.test("past_due on a paying (non-trial) subscription leaves entitlement blank (no change)", () => {
  assertEquals(map(subscriptionEvent("customer.subscription.updated", { status: "past_due" })).entitlement, "");
});

Deno.test("cancel_at_period_end keeps access, tags reason", () => {
  const a = map(subscriptionEvent("customer.subscription.updated", { cancel_at_period_end: true }));
  assertEquals(a.entitlement, "premium");
  assertEquals(a.reason, "customer.subscription.updated:cancel_at_period_end");
});

Deno.test("subscription.deleted / canceled / unpaid -> free", () => {
  assertEquals(map(subscriptionEvent("customer.subscription.deleted", { status: "canceled" })).entitlement, "free");
  assertEquals(map(subscriptionEvent("customer.subscription.updated", { status: "unpaid" })).entitlement, "free");
});

Deno.test("deleted trial is a canceled transition", () => {
  const trialEnd = 1_800_000_000 - 100;
  const a = map(subscriptionEvent("customer.subscription.deleted", { status: "canceled", trial_end: trialEnd, ended_at: trialEnd + 10 }));
  assertEquals(a.trial_transition, "canceled");
});

Deno.test("invoice.payment_failed -> free; invoice.payment_succeeded -> premium via paid", () => {
  const failed = subscriptionEvent("invoice.payment_failed", {
    id: "in_1", subscription: "sub_1", status: "open", metadata: {},
    subscription_details: { metadata: { supabase_user_id: USER_ID } },
    lines: { data: [{ price: { id: PRICE_PRO_MONTHLY } }] },
  });
  assertEquals(map(failed).entitlement, "free");
  const ok = subscriptionEvent("invoice.payment_succeeded", {
    id: "in_2", subscription: "sub_1", paid: true, status: "paid", metadata: {}, items: undefined,
    subscription_details: { metadata: { supabase_user_id: USER_ID } },
    lines: { data: [{ price: { id: PRICE_PRO_ANNUAL } }] },
  });
  const a = map(ok);
  assertEquals(a.entitlement, "premium");
  assertEquals(a.stripe_subscription_id, "sub_1");
  assertEquals(a.stripe_price_id, PRICE_PRO_ANNUAL);
  assertEquals(a.stripe_subscription_status, "active");
});

Deno.test("checkout.session.completed: client_reference_id is the user id; no_payment_required => trial started", () => {
  const e = subscriptionEvent("checkout.session.completed", {
    id: "cs_1", status: "complete", subscription: "sub_9", metadata: {}, client_reference_id: USER_ID,
    payment_status: "no_payment_required", items: undefined,
  });
  const a = map(e);
  assertEquals(a.user_id, USER_ID);
  assertEquals(a.entitlement, "premium");
  assertEquals(a.stripe_subscription_id, "sub_9");
  assertEquals(a.trial_transition, "started");
});

Deno.test("unrelated event types resolve no entitlement", () => {
  assertEquals(map(subscriptionEvent("customer.created")).entitlement, "");
});

Deno.test("profile payload: fields, trial_ends_at set/cleared only on subscription events", () => {
  const trialEnd = 1_800_000_000 + 86400;
  const a = map(subscriptionEvent("customer.subscription.updated", { status: "trialing", trial_end: trialEnd }));
  const p = buildProfileEntitlementPayload(a, NOW);
  assertEquals(p.entitlement, "premium");
  assertEquals(p.stripe_customer_id, "cus_1");
  assertEquals(p.stripe_event_id, "evt_1");
  assertEquals(p.trial_ends_at, new Date(trialEnd * 1000).toISOString());
  assertEquals(p.stripe_event_created_at, new Date(1_800_000_000 * 1000).toISOString());
  const cleared = buildProfileEntitlementPayload(map(subscriptionEvent("customer.subscription.updated")), NOW);
  assertEquals(cleared.trial_ends_at, null);
  const checkout = buildProfileEntitlementPayload(map(subscriptionEvent("checkout.session.completed", { status: "complete" })), NOW);
  assert(!("trial_ends_at" in checkout));
});

Deno.test("ordering guard: grants only strictly newer; revocations may tie", () => {
  const grant = durableEventOrderingParams({ entitlement: "premium", stripe_event_id: "evt_1", stripe_event_created_at: "2027-01-01T00:00:00.000Z" });
  assert(!grant.or.includes("stripe_event_created_at.eq"));
  assert(grant.or.includes("stripe_event_created_at.lt.2027-01-01T00:00:00.000Z"));
  const revoke = durableEventOrderingParams({ entitlement: "free", stripe_event_id: "evt_1", stripe_event_created_at: "2027-01-01T00:00:00.000Z" });
  assert(revoke.or.includes("stripe_event_created_at.eq.2027-01-01T00:00:00.000Z"));
  assertEquals(durableEventOrderingParams({ entitlement: "free" }), {});
});

Deno.test("price allowlist: live mode rejects a signed grant for an unlisted price", async () => {
  const store = new FakeStore();
  const live = stripeConfig({ billingMode: "live" });
  const bad = subscriptionEvent("customer.subscription.updated", { items: { data: [{ price: { id: "price_attacker" } }] } });
  const r = await processStripeEvent(bad, live, store);
  assertEquals(r.skipped, true);
  assertEquals(r.action.entitlement, "");
  assertEquals(store.updates.length, 0);
  const good = await processStripeEvent(subscriptionEvent("customer.subscription.updated"), live, store);
  assertEquals(good.ok, true);
  assertEquals(store.updates.length, 1);
  assertEquals(allowedPriceIds(stripeConfig({ priceFrontOfficeAnnual: "" })).has(PRICE_FO), false);
});

Deno.test("price allowlist: live with no configured prices grants nothing", async () => {
  const store = new FakeStore();
  const cfg = stripeConfig({ billingMode: "live", priceMonthly: "", priceAnnual: "", priceProAnnualLaunchWeek: "", priceFrontOfficeAnnual: "" });
  const r = await processStripeEvent(subscriptionEvent("customer.subscription.updated"), cfg, store);
  assertEquals(r.skipped, true);
  assertEquals(store.updates.length, 0);
});

Deno.test("idempotent by event id: second delivery performs no second update", async () => {
  const store = new FakeStore();
  const ev = subscriptionEvent("customer.subscription.updated");
  const first = await processStripeEvent(ev, stripeConfig(), store, { now: NOW });
  const second = await processStripeEvent(ev, stripeConfig(), store, { now: NOW });
  assertEquals(first.duplicate, undefined);
  assertEquals(second.duplicate, true);
  assertEquals(second.skipped, true);
  assertEquals(store.updates.length, 1);
});

Deno.test("failed profile update is NOT recorded (so Stripe retry can succeed)", async () => {
  const store = new FakeStore();
  store.failUpdate = "Supabase entitlement update failed.";
  const r = await processStripeEvent(subscriptionEvent("customer.subscription.updated"), stripeConfig(), store, { now: NOW });
  assertEquals(r.ok, false);
  assertEquals(store.recorded.length, 0);
  store.failUpdate = "";
  const retry = await processStripeEvent(subscriptionEvent("customer.subscription.updated"), stripeConfig(), store, { now: NOW });
  assertEquals(retry.ok, true);
  assertEquals(store.updates.length, 1);
});

Deno.test("non-entitlement events are skipped and recorded; missing/invalid user id fails with 'user id'", async () => {
  const store = new FakeStore();
  const skip = await processStripeEvent(subscriptionEvent("customer.created"), stripeConfig(), store);
  assertEquals(skip.skipped, true);
  assertEquals(store.recorded.length, 1);
  const noUser = await processStripeEvent(
    subscriptionEvent("customer.subscription.updated", { metadata: {} }, { id: "evt_nouser" }),
    stripeConfig(),
    store,
  );
  assertEquals(noUser.ok, false);
  assert(noUser.error.includes("user id"));
  const badUser = await processStripeEvent(
    subscriptionEvent("customer.subscription.updated", { metadata: { supabase_user_id: "x' or 1=1" } }, { id: "evt_baduser" }),
    stripeConfig(),
    store,
  );
  assertEquals(badUser.ok, false);
});
