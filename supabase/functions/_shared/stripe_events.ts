// Port of modules/stripe_billing.py (map_stripe_event_to_entitlement and helpers)
// and modules/stripe_webhook.py (payload building, ordering guard, price
// allowlist, processing flow). Behavior is intentionally identical.

import { StripeConfig, SUPPORTED_ENTITLEMENT_VALUES } from "./config.ts";
import { epoch, isoFromEpoch, isObj, isUuid, Json, st } from "./util.ts";

export const ACTIVE_ENTITLEMENT_EVENTS = new Set([
  "checkout.session.completed",
  "customer.subscription.created",
  "customer.subscription.updated",
  "invoice.payment_succeeded",
]);
export const INACTIVE_ENTITLEMENT_EVENTS = new Set(["customer.subscription.deleted"]);

export interface StripeAction {
  event_id: string;
  event_created: string;
  user_id: string;
  entitlement: string;
  reason: string;
  stripe_customer_id: string;
  stripe_subscription_id: string;
  stripe_subscription_status: string;
  stripe_price_id: string;
  cancel_at_period_end: string;
  stripe_trial_end: string;
  trial_transition: string;
}

function eventObject(event: Json): Json {
  const data = isObj(event.data) ? event.data : {};
  return isObj(data.object) ? data.object : {};
}

function metadataUserId(obj: Json): string {
  const metadata = isObj(obj.metadata) ? obj.metadata : {};
  const subMeta = isObj(obj.subscription_details) && isObj(obj.subscription_details.metadata)
    ? obj.subscription_details.metadata
    : {};
  const customer = isObj(obj.customer) ? obj.customer : {};
  const customerMeta = isObj(customer.metadata) ? customer.metadata : {};
  return st(
    metadata.supabase_user_id || subMeta.supabase_user_id || customerMeta.supabase_user_id ||
      obj.client_reference_id,
  );
}

function priceIdFromList(list: unknown, key: "price"): string {
  const container = isObj(list) ? list : {};
  const data = Array.isArray(container.data) ? container.data : [];
  for (const item of data) {
    if (!isObj(item)) continue;
    const price = isObj(item[key]) ? item[key] as Json : {};
    const id = st(price.id);
    if (id) return id;
  }
  return "";
}

export function stripePriceId(obj: Json): string {
  if (isObj(obj.price)) {
    const id = st(obj.price.id);
    if (id) return id;
  }
  return priceIdFromList(obj.items, "price") || priceIdFromList(obj.lines, "price");
}

function stripeId(value: unknown): string {
  return isObj(value) ? st(value.id) : st(value);
}

function invoiceSubscriptionStatus(obj: Json): string {
  const billingReason = st(obj.billing_reason).toLowerCase();
  const status = st(obj.status).toLowerCase();
  if (obj.paid === true || status === "paid") return "active";
  if (billingReason) return status || billingReason;
  return status;
}

function trialTransition(eventType: string, obj: Json, event: Json, status: string, trialEnd: number | null): string {
  const data = isObj(event.data) ? event.data : null;
  const previous = data && isObj(data.previous_attributes) ? data.previous_attributes : null;
  const previousStatus = previous ? st(previous.status).toLowerCase() : "";
  if (eventType === "customer.subscription.created" && status === "trialing") return "started";
  if (eventType === "checkout.session.completed" && st(obj.payment_status) === "no_payment_required") return "started";
  if (eventType === "customer.subscription.updated" && previousStatus === "trialing") {
    if (status === "active") return "converted";
    if (["canceled", "unpaid", "incomplete_expired", "past_due"].includes(status)) return "canceled";
  }
  if (eventType === "customer.subscription.deleted" && trialEnd !== null) {
    const ended = epoch(obj.ended_at) ?? epoch(obj.canceled_at);
    if (previousStatus === "trialing" || (ended !== null && ended <= trialEnd + 300)) return "canceled";
  }
  return "";
}

/** Resolve one Stripe event to a profiles.entitlement write (raw values: free | premium | front_office). */
export function mapStripeEventToEntitlement(
  event: Json,
  opts: { config?: StripeConfig; now?: Date } = {},
): StripeAction {
  const eventType = st(event.type);
  const obj = eventObject(event);
  const userId = metadataUserId(obj);
  let status = st(obj.status).toLowerCase();
  if (eventType.startsWith("invoice.")) status = invoiceSubscriptionStatus(obj);
  const customerId = stripeId(obj.customer);
  const subscriptionId = stripeId(obj.subscription || obj.id);
  const priceId = stripePriceId(obj);

  let entitlement = "";
  let reason = eventType;
  const cancelAtPeriodEnd = !!obj.cancel_at_period_end;
  const trialEnd = epoch(obj.trial_end);
  const nowSeconds = Math.floor((opts.now ?? new Date()).getTime() / 1000);
  const trialExpired = status === "trialing" && trialEnd !== null && trialEnd <= nowSeconds;

  if (ACTIVE_ENTITLEMENT_EVENTS.has(eventType)) {
    if (!status || ["active", "trialing", "paid", "complete"].includes(status)) {
      entitlement = "premium";
      const fo = opts.config?.priceFrontOfficeAnnual;
      if (opts.config && fo && priceId && priceId === fo) entitlement = "front_office";
      if (cancelAtPeriodEnd && (status === "active" || status === "trialing")) {
        reason = `${eventType}:cancel_at_period_end`;
      }
    }
  }
  if (trialExpired) {
    entitlement = "free";
    reason = `${eventType}:trial_expired`;
  }
  if (eventType === "invoice.payment_failed") entitlement = "free";
  if (INACTIVE_ENTITLEMENT_EVENTS.has(eventType) || ["canceled", "unpaid", "incomplete_expired"].includes(status)) {
    entitlement = "free";
  }

  const transition = trialTransition(eventType, obj, event, status, trialEnd);
  if (transition === "canceled" && eventType === "customer.subscription.updated") {
    entitlement = "free";
    reason = `${eventType}:trial_ended_unpaid`;
  }

  return {
    event_id: st(event.id),
    event_created: st(event.created),
    user_id: userId,
    entitlement,
    reason,
    stripe_customer_id: customerId,
    stripe_subscription_id: subscriptionId,
    stripe_subscription_status: status,
    stripe_price_id: priceId,
    cancel_at_period_end: cancelAtPeriodEnd ? "true" : "false",
    stripe_trial_end: status === "trialing" && !trialExpired ? isoFromEpoch(trialEnd) : "",
    trial_transition: transition,
  };
}

// ---- profile payload + ordering guard (modules/stripe_webhook.py) ----

export class UpdateError extends Error {}
export const NOOP = "noop";

export type ProfilePayload = Record<string, string | null>;

export function buildProfileEntitlementPayload(action: Partial<StripeAction>, now: Date = new Date()): ProfilePayload {
  const entitlement = st(action.entitlement).toLowerCase();
  if (entitlement && !SUPPORTED_ENTITLEMENT_VALUES.has(entitlement)) {
    throw new UpdateError("Stripe event did not produce a supported entitlement update.");
  }
  const payload: ProfilePayload = { premium_updated_at: now.toISOString() };
  if (SUPPORTED_ENTITLEMENT_VALUES.has(entitlement)) payload.entitlement = entitlement;
  const optional: Record<string, unknown> = {
    stripe_customer_id: action.stripe_customer_id,
    stripe_subscription_id: action.stripe_subscription_id,
    stripe_subscription_status: action.stripe_subscription_status,
    stripe_price_id: action.stripe_price_id,
    stripe_event_id: action.event_id,
  };
  for (const [k, v] of Object.entries(optional)) {
    const clean = st(v);
    if (clean) payload[k] = clean;
  }
  // Only subscription lifecycle events are authoritative about trial end;
  // any non-trialing state clears it (null).
  if (st(action.reason).startsWith("customer.subscription.")) {
    payload.trial_ends_at = st((action as StripeAction).stripe_trial_end) || null;
  }
  const created = st(action.event_created);
  if (created) {
    const n = Number(created);
    const d = Number.isFinite(n) && created !== "" ? new Date(n * 1000) : null;
    if (!d || Number.isNaN(d.getTime())) throw new UpdateError("Stripe event timestamp is invalid.");
    payload.stripe_event_created_at = d.toISOString();
  }
  if (!("entitlement" in payload) && Object.keys(payload).length === 1) throw new UpdateError(NOOP);
  return payload;
}

/** PostgREST `or` filter: atomic out-of-order guard. Same clauses as the Python port source. */
export function durableEventOrderingParams(payload: ProfilePayload): Record<string, string> {
  const createdAt = st(payload.stripe_event_created_at);
  const eventId = st(payload.stripe_event_id);
  if (!createdAt) return {};
  const identity = eventId ? `or(stripe_event_id.is.null,stripe_event_id.neq.${eventId})` : "";
  const clauses = [
    identity ? `and(stripe_event_created_at.is.null,${identity})` : "stripe_event_created_at.is.null",
    identity
      ? `and(stripe_event_created_at.lt.${createdAt},${identity})`
      : `stripe_event_created_at.lt.${createdAt}`,
  ];
  if (st(payload.entitlement).toLowerCase() === "free" && eventId) {
    clauses.push(
      `and(stripe_event_created_at.eq.${createdAt},or(stripe_event_id.is.null,stripe_event_id.neq.${eventId}))`,
    );
  }
  return { or: `(${clauses.join(",")})` };
}

/** Live-mode price allowlist: a signed paid grant must belong to a configured plan. */
export function allowedPriceIds(config: StripeConfig): Set<string> {
  return new Set(
    [config.priceMonthly, config.priceAnnual, config.priceProAnnualLaunchWeek, config.priceFrontOfficeAnnual]
      .map(st).filter(Boolean),
  );
}

// ---- processing flow ----

export interface BillingStore {
  /** Has this (provider, event id) been fully processed already? */
  eventSeen(provider: string, eventId: string): Promise<boolean>;
  recordEvent(row: {
    provider: string;
    event_id: string;
    event_type: string;
    user_id: string;
    outcome: string;
    entitlement: string;
    reason: string;
    trial_transition: string;
  }): Promise<void>;
  /** PATCH profiles. Returns {ok, error}. Implements the trial_ends_at column-missing retry. */
  updateProfile(userId: string, payload: ProfilePayload, orderingParams: Record<string, string>): Promise<{ ok: boolean; error: string }>;
}

export interface ProcessResult {
  ok: boolean;
  skipped: boolean;
  duplicate?: boolean;
  error: string;
  event_id: string;
  action: Partial<StripeAction>;
}

export async function processStripeEvent(
  event: Json,
  config: StripeConfig,
  store: BillingStore,
  opts: { now?: Date } = {},
): Promise<ProcessResult> {
  const action = mapStripeEventToEntitlement(event, { config, now: opts.now });
  const eventId = st(action.event_id);
  if (eventId && await store.eventSeen("stripe", eventId)) {
    return { ok: true, skipped: true, duplicate: true, error: "", event_id: eventId, action };
  }
  const entitlement = st(action.entitlement).toLowerCase();
  const record = (outcome: string) =>
    eventId
      ? store.recordEvent({
        provider: "stripe",
        event_id: eventId,
        event_type: st(event.type),
        user_id: action.user_id,
        outcome,
        entitlement,
        reason: action.reason,
        trial_transition: action.trial_transition,
      })
      : Promise.resolve();

  if ((entitlement === "premium" || entitlement === "front_office") && config.billingMode === "live") {
    const allowed = allowedPriceIds(config);
    if (allowed.size === 0 || !allowed.has(st(action.stripe_price_id))) {
      // Signed but not on an allowlisted plan: no grant. Not recorded, so a
      // later fix of the allowlist + Stripe "resend" can still apply it.
      return { ok: true, skipped: true, error: "", event_id: eventId, action: { ...action, entitlement: "" } };
    }
  }
  if (!SUPPORTED_ENTITLEMENT_VALUES.has(entitlement)) {
    await record("skipped_no_entitlement");
    return { ok: true, skipped: true, error: "", event_id: eventId, action };
  }

  // update_profile_entitlement
  const userId = st(action.user_id);
  let ok = true;
  let error = "";
  if (!userId || !isUuid(userId)) {
    ok = false;
    error = "Stripe event did not include a Supabase user id.";
  } else {
    let payload: ProfilePayload | null = null;
    try {
      payload = buildProfileEntitlementPayload(action, opts.now);
    } catch (e) {
      if (e instanceof UpdateError && e.message === NOOP) payload = null;
      else {
        ok = false;
        error = (e as Error).message;
      }
    }
    if (ok && payload && "entitlement" in payload) {
      const res = await store.updateProfile(userId, payload, durableEventOrderingParams(payload));
      ok = res.ok;
      error = res.error;
    }
  }
  if (ok) await record("applied");
  return {
    ok,
    skipped: false,
    error,
    event_id: eventId,
    action: ok ? action : { user_id: action.user_id, entitlement: action.entitlement, reason: action.reason },
  };
}

/** Mirror of services/stripe_webhook_service.py `_assert_billing_runtime` + mode checks. Returns an error or "". */
export function assertStripeRuntime(config: StripeConfig): { status: number; error: string } | null {
  const modeOk = (config.billingMode === "test" || config.billingMode === "live") &&
    config.secretKey.startsWith(`sk_${config.billingMode}_`);
  // The webhook does not need the secret key to verify signatures, but when one
  // is present it must match the mode (construct_stripe_event parity).
  if (config.secretKey && !modeOk) return { status: 503, error: "Stripe billing mode and secret key do not match." };
  if (config.billingMode !== "test" && config.billingMode !== "live") {
    return { status: 503, error: "Stripe billing mode and secret key do not match." };
  }
  if (config.billingMode === "live" && !(config.priceMonthly && config.priceAnnual)) {
    return { status: 503, error: "Stripe live price configuration is incomplete." };
  }
  if (!config.webhookSecret || !config.webhookSecret.startsWith("whsec_")) {
    return { status: 500, error: "Stripe webhook secret is not configured." };
  }
  return null;
}
