// Supabase access via plain fetch (PostgREST + GoTrue). Uses the service-role
// key that the platform injects into every Edge Function; it never leaves the
// function runtime. `fetchFn` is injectable so tests never touch the network.

import { SupabaseConfig } from "./config.ts";
import { BillingStore, ProfilePayload } from "./stripe_events.ts";
import { HttpError, isObj, Json, st } from "./util.ts";

export type FetchFn = (input: string, init?: RequestInit) => Promise<Response>;

function serviceHeaders(cfg: SupabaseConfig, extra: Record<string, string> = {}): Record<string, string> {
  return {
    apikey: cfg.serviceRoleKey,
    Authorization: `Bearer ${cfg.serviceRoleKey}`,
    "Content-Type": "application/json",
    ...extra,
  };
}

async function errorMessage(res: Response): Promise<string> {
  try {
    const data = await res.json();
    if (isObj(data)) {
      for (const k of ["message", "hint", "details", "code"]) {
        const v = st(data[k]);
        if (v) return v;
      }
    }
  } catch { /* fall through */ }
  return "";
}

/** PATCH public.profiles for one user. Port of update_profile_entitlement's HTTP half. */
export function profilePatcher(
  cfg: SupabaseConfig,
  fetchFn: FetchFn,
  columnHint: { provider: string; columns: string[]; sqlFile: string },
) {
  return async (
    userId: string,
    payload: ProfilePayload,
    orderingParams: Record<string, string>,
  ): Promise<{ ok: boolean; error: string }> => {
    const url = (body: ProfilePayload) => {
      void body;
      const q = new URLSearchParams({ user_id: `eq.${userId}`, ...orderingParams });
      return `${cfg.url}/rest/v1/profiles?${q.toString()}`;
    };
    const patch = (body: ProfilePayload) =>
      fetchFn(url(body), {
        method: "PATCH",
        headers: serviceHeaders(cfg, { Prefer: "return=minimal" }),
        body: JSON.stringify(body),
      });
    let res: Response;
    try {
      res = await patch(payload);
      if (res.status >= 400 && "trial_ends_at" in payload) {
        const msg = (await errorMessage(res.clone())).toLowerCase();
        if (msg.includes("trial_ends_at")) {
          // docs/supabase_free_trial.sql not applied: entitlement must still flow.
          const { trial_ends_at: _drop, ...rest } = payload;
          res = await patch(rest);
        }
      }
    } catch {
      return { ok: false, error: "Could not reach Supabase profiles table." };
    }
    if (res.status >= 400) {
      const lowered = (await errorMessage(res)).toLowerCase();
      if (lowered.includes("column") && columnHint.columns.some((c) => lowered.includes(c))) {
        return {
          ok: false,
          error: `Supabase profiles billing columns are missing. Run ${columnHint.sqlFile} before enabling the ${columnHint.provider} webhook.`,
        };
      }
      return { ok: false, error: "Supabase entitlement update failed." };
    }
    return { ok: true, error: "" };
  };
}

/** Durable idempotency log: public.billing_webhook_events (docs/supabase_billing_edge.sql). */
export function eventLog(cfg: SupabaseConfig, fetchFn: FetchFn) {
  return {
    async eventSeen(provider: string, eventId: string): Promise<boolean> {
      const q = new URLSearchParams({
        provider: `eq.${provider}`,
        event_id: `eq.${eventId}`,
        select: "event_id",
        limit: "1",
      });
      const res = await fetchFn(`${cfg.url}/rest/v1/billing_webhook_events?${q}`, {
        headers: serviceHeaders(cfg),
      });
      if (res.status >= 400) throw new HttpError(500, "Could not read webhook event log.");
      const rows = await res.json();
      return Array.isArray(rows) && rows.length > 0;
    },
    async recordEvent(row: Json): Promise<void> {
      const res = await fetchFn(`${cfg.url}/rest/v1/billing_webhook_events?on_conflict=provider,event_id`, {
        method: "POST",
        headers: serviceHeaders(cfg, { Prefer: "resolution=ignore-duplicates,return=minimal" }),
        body: JSON.stringify(row),
      });
      // A failed log write must not fail the webhook: the profile update already
      // committed and its own ordering guard keeps replays harmless.
      if (res.status >= 400) console.error("billing_webhook_events insert failed", res.status);
    },
  };
}

export function stripeStore(cfg: SupabaseConfig, fetchFn: FetchFn): BillingStore {
  const log = eventLog(cfg, fetchFn);
  return {
    eventSeen: log.eventSeen,
    recordEvent: log.recordEvent,
    updateProfile: profilePatcher(cfg, fetchFn, {
      provider: "Stripe",
      sqlFile: "docs/supabase_stripe_billing.sql",
      columns: [
        "stripe_customer_id",
        "stripe_subscription_id",
        "stripe_subscription_status",
        "stripe_price_id",
        "premium_updated_at",
        "stripe_event_id",
        "stripe_event_created_at",
        "entitlement",
      ],
    }),
  };
}

// ---- user auth + profile reads for checkout / portal ----

export interface VerifiedUser {
  id: string;
  email: string;
}

/** Verify the caller's Supabase JWT with GoTrue. Email comes from here, never from the request body. */
export async function verifyUserJwt(cfg: SupabaseConfig, fetchFn: FetchFn, authorization: string): Promise<VerifiedUser> {
  const m = /^Bearer\s+(.+)$/i.exec(st(authorization));
  if (!m) throw new HttpError(401, "Sign in to continue.");
  const res = await fetchFn(`${cfg.url}/auth/v1/user`, {
    headers: { apikey: cfg.anonKey || cfg.serviceRoleKey, Authorization: `Bearer ${m[1].trim()}` },
  });
  if (res.status !== 200) throw new HttpError(401, "Sign in to continue.");
  const user = await res.json();
  const id = isObj(user) ? st(user.id) : "";
  if (!id) throw new HttpError(401, "Sign in to continue.");
  return { id, email: isObj(user) ? st(user.email) : "" };
}

/** Billing-history columns for trial eligibility, progressively narrower for older schemas. Returns null if unreadable. */
const TRIAL_PROFILE_SELECTS = [
  "stripe_customer_id,stripe_subscription_id,stripe_subscription_status,revenuecat_app_user_id,trial_ends_at",
  "stripe_customer_id,stripe_subscription_id,stripe_subscription_status",
  "stripe_customer_id,stripe_subscription_id",
];

export async function fetchBillingProfile(cfg: SupabaseConfig, fetchFn: FetchFn, userId: string): Promise<Json | null> {
  for (const select of TRIAL_PROFILE_SELECTS) {
    const q = new URLSearchParams({ user_id: `eq.${userId}`, select, limit: "1" });
    const res = await fetchFn(`${cfg.url}/rest/v1/profiles?${q}`, { headers: serviceHeaders(cfg) });
    if (res.status < 400) {
      const rows = await res.json();
      return Array.isArray(rows) && isObj(rows[0]) ? rows[0] : {};
    }
  }
  return null;
}

export function revenueCatStore(cfg: SupabaseConfig, fetchFn: FetchFn): BillingStore {
  const log = eventLog(cfg, fetchFn);
  return {
    eventSeen: log.eventSeen,
    recordEvent: log.recordEvent,
    updateProfile: profilePatcher(cfg, fetchFn, {
      provider: "RevenueCat",
      sqlFile: "docs/supabase_revenuecat_billing.sql",
      columns: [
        "revenuecat_app_user_id",
        "revenuecat_event_id",
        "revenuecat_event_type",
        "revenuecat_environment",
        "revenuecat_event_created_at",
        "premium_updated_at",
        "entitlement",
      ],
    }),
  };
}
