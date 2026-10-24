// Port of modules/revenuecat_billing.py + modules/revenuecat_webhook.py.
// Entitlement is NEVER inferred from the event body: every verified event
// triggers a fresh "active entitlements" read from the RevenueCat API.

import {
  RevenueCatConfig,
  rcApiConfigured,
  rcExpectedEnvironment,
  SUPPORTED_ENTITLEMENT_VALUES,
} from "./config.ts";
import { BillingStore, ProfilePayload } from "./stripe_events.ts";
import { FetchFn } from "./supabase_rest.ts";
import { HttpError, isObj, isUuid, Json, pyInt, st, timingSafeEqual } from "./util.ts";

export class RevenueCatAuthError extends Error {}
export class RevenueCatPayloadError extends Error {}
export class RevenueCatUpstreamError extends Error {}

export function verifyWebhookAuthorization(header: string | null, config: RevenueCatConfig): void {
  if (!config.webhookAuthToken) throw new HttpError(500, "RevenueCat webhook auth token is not configured.");
  const provided = st(header);
  if (!provided || !timingSafeEqual(provided, config.webhookAuthToken)) {
    throw new RevenueCatAuthError("Invalid RevenueCat webhook authorization.");
  }
}

export function parseWebhookPayload(raw: string): Json {
  let data: unknown;
  try {
    data = JSON.parse(raw);
  } catch {
    throw new RevenueCatPayloadError("RevenueCat webhook payload is not valid JSON.");
  }
  const event = isObj(data) ? data.event : null;
  if (!isObj(event)) throw new RevenueCatPayloadError("RevenueCat webhook payload is missing an event.");
  return event;
}

export async function fetchActiveEntitlementLookupKeys(
  appUserId: string,
  config: RevenueCatConfig,
  fetchFn: FetchFn,
): Promise<Set<string>> {
  if (!rcApiConfigured(config)) throw new RevenueCatUpstreamError("RevenueCat API is not configured.");
  const res = await fetchFn(
    `https://api.revenuecat.com/v2/projects/${config.projectId}/customers/${encodeURIComponent(st(appUserId))}/active_entitlements`,
    { headers: { Authorization: `Bearer ${config.secretKey}` } },
  );
  if (res.status === 404) return new Set();
  if (res.status >= 400) throw new RevenueCatUpstreamError("Could not read RevenueCat customer entitlements.");
  const data = await res.json();
  const items = isObj(data) && Array.isArray(data.items) ? data.items : [];
  const keys = new Set<string>();
  for (const item of items) {
    if (!isObj(item)) continue;
    for (const f of ["lookup_key", "id"]) {
      const v = st(item[f]);
      if (v) keys.add(v);
    }
  }
  return keys;
}

function trialFields(event: Json, entitlement: string): Record<string, string> {
  const eventType = st(event.type);
  const periodType = st(event.period_type).toUpperCase();
  const out: Record<string, string> = {};
  if (!periodType) return out;
  out.period_type = periodType;
  let trialEnd = "";
  if (periodType === "TRIAL" && (entitlement === "premium" || entitlement === "front_office")) {
    const ms = pyInt(event.expiration_at_ms);
    const d = ms === null ? null : new Date(ms);
    trialEnd = d && !Number.isNaN(d.getTime()) ? d.toISOString() : "";
  }
  out.trial_ends_at = trialEnd;
  let transition = "";
  if (periodType === "TRIAL" && eventType === "INITIAL_PURCHASE") transition = "started";
  else if (
    (eventType === "RENEWAL" || eventType === "INITIAL_PURCHASE") &&
    (event.is_trial_conversion === true || st(event.is_trial_conversion).toLowerCase() === "true")
  ) transition = "converted";
  else if (periodType === "TRIAL" && (eventType === "CANCELLATION" || eventType === "EXPIRATION")) transition = "canceled";
  out.trial_transition = transition;
  const store = st(event.store).toUpperCase();
  out.platform = ({ APP_STORE: "ios", MAC_APP_STORE: "ios", PLAY_STORE: "android" } as Record<string, string>)[store] ?? "";
  return out;
}

export interface RevenueCatAction extends Record<string, string> {
  event_id: string;
  event_type: string;
  user_id: string;
  environment: string;
  entitlement: string;
  reason: string;
}

export async function mapRevenueCatEvent(event: Json, config: RevenueCatConfig, fetchFn: FetchFn): Promise<RevenueCatAction> {
  const eventType = st(event.type);
  const appUserId = st(event.app_user_id);
  const environment = st(event.environment).toUpperCase();
  const result: RevenueCatAction = {
    event_id: st(event.id),
    event_type: eventType,
    user_id: appUserId,
    environment,
    entitlement: "",
    reason: eventType,
  };
  if (event.event_timestamp_ms !== null && event.event_timestamp_ms !== undefined) {
    const ms = pyInt(event.event_timestamp_ms);
    if (ms !== null) result.event_created_ms = String(ms);
  }
  if (eventType === "TEST") {
    result.reason = "test_event";
    return result;
  }
  if (environment && environment !== rcExpectedEnvironment(config)) {
    result.reason = "environment_mismatch";
    return result;
  }
  if (!appUserId) {
    result.reason = "missing_app_user_id";
    return result;
  }
  const active = await fetchActiveEntitlementLookupKeys(appUserId, config, fetchFn);
  if (active.has(config.frontOfficeEntitlementLookupKey)) result.entitlement = "front_office";
  else if (active.has(config.entitlementLookupKey)) result.entitlement = "premium";
  else result.entitlement = "free";
  Object.assign(result, trialFields(event, result.entitlement));
  return result;
}

export function buildRevenueCatPayload(action: Record<string, string>, now: Date = new Date()): ProfilePayload {
  const entitlement = st(action.entitlement).toLowerCase();
  if (entitlement && !SUPPORTED_ENTITLEMENT_VALUES.has(entitlement)) {
    throw new Error("RevenueCat event did not produce a supported entitlement update.");
  }
  const payload: ProfilePayload = { premium_updated_at: now.toISOString() };
  if (SUPPORTED_ENTITLEMENT_VALUES.has(entitlement)) payload.entitlement = entitlement;
  const optional: Record<string, unknown> = {
    revenuecat_app_user_id: action.user_id,
    revenuecat_event_id: action.event_id,
    revenuecat_event_type: action.event_type,
    revenuecat_environment: action.environment,
  };
  for (const [k, v] of Object.entries(optional)) {
    const clean = st(v);
    if (clean) payload[k] = clean;
  }
  if (st(action.period_type)) payload.trial_ends_at = st(action.trial_ends_at) || null;
  const ms = st(action.event_created_ms);
  if (ms) {
    const n = pyInt(ms);
    const d = n === null ? null : new Date(n);
    if (!d || Number.isNaN(d.getTime())) throw new Error("RevenueCat event timestamp is invalid.");
    payload.revenuecat_event_created_at = d.toISOString();
  }
  return payload;
}

export function revenueCatOrderingParams(payload: ProfilePayload): Record<string, string> {
  const createdAt = st(payload.revenuecat_event_created_at);
  const eventId = st(payload.revenuecat_event_id);
  if (!createdAt) return {};
  const identity = eventId ? `or(revenuecat_event_id.is.null,revenuecat_event_id.neq.${eventId})` : "";
  const clauses = [
    identity ? `and(revenuecat_event_created_at.is.null,${identity})` : "revenuecat_event_created_at.is.null",
    identity
      ? `and(revenuecat_event_created_at.lt.${createdAt},${identity})`
      : `revenuecat_event_created_at.lt.${createdAt}`,
  ];
  if (st(payload.entitlement).toLowerCase() === "free" && eventId) {
    clauses.push(
      `and(revenuecat_event_created_at.eq.${createdAt},or(revenuecat_event_id.is.null,revenuecat_event_id.neq.${eventId}))`,
    );
  }
  return { or: `(${clauses.join(",")})` };
}

export async function processRevenueCatEvent(
  event: Json,
  config: RevenueCatConfig,
  store: BillingStore,
  fetchFn: FetchFn,
  opts: { now?: Date } = {},
) {
  const action = await mapRevenueCatEvent(event, config, fetchFn);
  const eventId = st(action.event_id);
  if (eventId && await store.eventSeen("revenuecat", eventId)) {
    return { ok: true, skipped: true, duplicate: true, error: "", event_id: eventId, action };
  }
  const entitlement = st(action.entitlement).toLowerCase();
  const record = (outcome: string) =>
    eventId
      ? store.recordEvent({
        provider: "revenuecat",
        event_id: eventId,
        event_type: action.event_type,
        user_id: action.user_id,
        outcome,
        entitlement,
        reason: action.reason,
        trial_transition: st(action.trial_transition),
      })
      : Promise.resolve();
  if (!SUPPORTED_ENTITLEMENT_VALUES.has(entitlement)) {
    await record("skipped_no_entitlement");
    return { ok: true, skipped: true, error: "", event_id: eventId, action };
  }
  const userId = st(action.user_id);
  let ok = true;
  let error = "";
  if (userId && !isUuid(userId)) {
    // Anonymous RevenueCat ids ($RCAnonymousID:...) can never match a profile.
    // Acknowledge (200) instead of failing, otherwise RevenueCat retries forever.
    await record("skipped_non_uuid_user");
    return { ok: true, skipped: true, error: "", event_id: eventId, action: { ...action, reason: "non_uuid_app_user_id" } };
  }
  if (!userId) {
    ok = false;
    error = "RevenueCat event did not include a Supabase user id.";
  } else {
    try {
      const payload = buildRevenueCatPayload(action, opts.now);
      const res = await store.updateProfile(userId, payload, revenueCatOrderingParams(payload));
      ok = res.ok;
      error = res.error;
    } catch (e) {
      ok = false;
      error = (e as Error).message;
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
