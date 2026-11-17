// Subscription lifecycle against an in-memory profiles row that enforces the
// real PostgREST ordering filters the webhooks send. Stripe TEST-mode fixtures
// only; no network, no real keys.

import { assert, assertEquals } from "./assert.ts";
import { loadRevenueCatConfig } from "./config.ts";
import { processRevenueCatEvent } from "./revenuecat_events.ts";
import { BillingStore, ProfilePayload, processStripeEvent } from "./stripe_events.ts";
import { alreadySubscribed } from "../create-checkout-session/handler.ts";
import { BASE_ENV, envOf, j, stripeConfig, subscriptionEvent, USER_ID } from "./fixtures.ts";

type Row = Record<string, string | null>;

// ---- tiny PostgREST filter evaluator (is.null / lt / eq / neq / not.in, and/or) ----
function splitTop(s: string): string[] {
  const out: string[] = [];
  let depth = 0;
  let cur = "";
  for (const ch of s) {
    if (ch === "(") depth++;
    if (ch === ")") depth--;
    if (ch === "," && depth === 0) {
      out.push(cur);
      cur = "";
    } else cur += ch;
  }
  if (cur) out.push(cur);
  return out;
}

function evalExpr(expr: string, row: Row): boolean {
  const group = /^(and|or)\((.*)\)$/s.exec(expr);
  if (group) {
    const parts = splitTop(group[2]).map((p) => evalExpr(p, row));
    return group[1] === "and" ? parts.every(Boolean) : parts.some(Boolean);
  }
  const m = /^([a-z_]+)\.(is\.null|lt|eq|neq|not\.in)\.?(.*)$/s.exec(expr);
  if (!m) throw new Error(`unsupported filter ${expr}`);
  const v = row[m[1]] ?? null;
  const arg = m[3];
  switch (m[2]) {
    case "is.null": return v === null;
    case "lt": return v !== null && v < arg;
    case "eq": return v !== null && v === arg;
    case "neq": return v !== null && v !== arg;
    default: return v !== null && !splitTop(arg.slice(1, -1)).includes(v);
  }
}

class ProfileDb implements BillingStore {
  row: Row = { entitlement: "free" };
  seen = new Set<string>();
  patches = 0;
  eventSeen(p: string, id: string) {
    return Promise.resolve(this.seen.has(`${p}:${id}`));
  }
  recordEvent(r: Record<string, unknown>) {
    this.seen.add(`${r.provider}:${r.event_id}`);
    return Promise.resolve();
  }
  updateProfile(_u: string, payload: ProfilePayload, ordering: Record<string, string>) {
    // PostgREST filter params: the key is the operator, the value its parenthesised list.
    const allowed = Object.entries(ordering).every(([k, v]) => evalExpr(`${k}${v}`, this.row));
    if (allowed) {
      this.patches++;
      Object.assign(this.row, payload);
    }
    return Promise.resolve({ ok: true, error: "" });
  }
}

const cfg = stripeConfig();
const NOW = new Date(1_800_000_100 * 1000);
let seq = 0;
const ev = (type: string, created: number, sub: Record<string, unknown> = {}) =>
  subscriptionEvent(type, sub, { id: `evt_${++seq}`, created });
const apply = (db: ProfileDb, e: Record<string, unknown>) => processStripeEvent(e, cfg, db, { now: NOW });

Deno.test("out of order: a late 'active' update cannot undo a newer cancellation", async () => {
  const db = new ProfileDb();
  await apply(db, ev("customer.subscription.created", 1000));
  assertEquals(db.row.entitlement, "premium");
  await apply(db, ev("customer.subscription.deleted", 3000, { status: "canceled" }));
  assertEquals(db.row.entitlement, "free");
  await apply(db, ev("customer.subscription.updated", 2000, { status: "active" })); // delayed delivery
  assertEquals(db.row.entitlement, "free");
  assertEquals(db.row.stripe_subscription_status, "canceled");
});

Deno.test("out of order: events arriving newest-first still end on the newest state", async () => {
  const db = new ProfileDb();
  await apply(db, ev("customer.subscription.updated", 5000, { status: "active" }));
  await apply(db, ev("customer.subscription.created", 1000, { status: "incomplete" }));
  assertEquals(db.row.entitlement, "premium");
});

Deno.test("payment failure revokes, a later retry restores, a replayed failure is a no-op", async () => {
  const db = new ProfileDb();
  await apply(db, ev("checkout.session.completed", 1000));
  const failed = ev("invoice.payment_failed", 2000, { status: "open", subscription: "sub_1" });
  await apply(db, failed);
  assertEquals(db.row.entitlement, "free");
  await apply(db, ev("invoice.payment_succeeded", 3000, { status: "paid", paid: true, subscription: "sub_1" }));
  assertEquals(db.row.entitlement, "premium");
  const before = db.patches;
  const replay = await apply(db, failed);
  assert(replay.skipped && replay.duplicate);
  assertEquals(db.patches, before);
  assertEquals(db.row.entitlement, "premium");
});

Deno.test("an out-of-order stale payment_failed cannot revoke after a newer success", async () => {
  const db = new ProfileDb();
  await apply(db, ev("invoice.payment_succeeded", 3000, { status: "paid", paid: true }));
  await apply(db, ev("invoice.payment_failed", 2000, { status: "open" }));
  assertEquals(db.row.entitlement, "premium");
});

Deno.test("cancel_at_period_end keeps Pro until the subscription is deleted", async () => {
  const db = new ProfileDb();
  await apply(db, ev("customer.subscription.created", 1000));
  await apply(db, ev("customer.subscription.updated", 2000, { cancel_at_period_end: true }));
  assertEquals(db.row.entitlement, "premium");
  await apply(db, ev("customer.subscription.deleted", 3000, { status: "canceled", cancel_at_period_end: true }));
  assertEquals(db.row.entitlement, "free");
});

// ---- cross-provider carry-over ----
const rcCfg = loadRevenueCatConfig(envOf(BASE_ENV));
const rcFetch = (active: string[]) => () => Promise.resolve(j({ items: active.map((k) => ({ lookup_key: k })) }));
const rcEvent = (type: string, ms: number) => ({
  id: `rc_${++seq}`,
  type,
  app_user_id: USER_ID,
  environment: "SANDBOX",
  event_timestamp_ms: ms,
});
const applyRc = (db: ProfileDb, e: Record<string, unknown>, active: string[]) =>
  processRevenueCatEvent(e, rcCfg, db, rcFetch(active) as never, { now: NOW });

Deno.test("carry-over: a lapsed App Store subscription cannot strip Pro bought on the web", async () => {
  const db = new ProfileDb();
  await apply(db, ev("customer.subscription.created", 1000));
  assertEquals(db.row.entitlement, "premium");
  await applyRc(db, rcEvent("EXPIRATION", 9_000_000_000_000), []); // newer than the Stripe event
  assertEquals(db.row.entitlement, "premium");
});

Deno.test("carry-over: once the Stripe subscription ends, the store decides", async () => {
  const db = new ProfileDb();
  await apply(db, ev("customer.subscription.created", 1000));
  await apply(db, ev("customer.subscription.deleted", 2000, { status: "canceled" }));
  assertEquals(db.row.entitlement, "free");
  await applyRc(db, rcEvent("INITIAL_PURCHASE", 3_000_000), ["premium"]);
  assertEquals(db.row.entitlement, "premium");
  await applyRc(db, rcEvent("EXPIRATION", 4_000_000), []);
  assertEquals(db.row.entitlement, "free");
});

Deno.test("carry-over: a store-only subscriber is downgraded normally", async () => {
  const db = new ProfileDb();
  await applyRc(db, rcEvent("INITIAL_PURCHASE", 1_000_000), ["premium"]);
  assertEquals(db.row.entitlement, "premium");
  await applyRc(db, rcEvent("EXPIRATION", 2_000_000), []);
  assertEquals(db.row.entitlement, "free");
});

Deno.test("checkout guard: refused for Stripe/trial/App Store Pro; allowed for Free and cancelled", () => {
  assert(alreadySubscribed({ stripe_subscription_status: "active" }));
  assert(alreadySubscribed({ stripe_subscription_status: "trialing" }));
  assert(alreadySubscribed({ entitlement: "premium" }));
  assert(alreadySubscribed({ entitlement: "front_office" }));
  assertEquals(alreadySubscribed({ entitlement: "free", stripe_subscription_status: "canceled" }), "");
  assertEquals(alreadySubscribed({}), "");
  assertEquals(alreadySubscribed(null), "");
});
