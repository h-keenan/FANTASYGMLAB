// Cancel every live Stripe subscription for an account that is being deleted.
// Idempotent (already-canceled / missing subscriptions are skipped, the DELETE
// carries an idempotency key) and failure-safe: any other Stripe failure
// THROWS so the caller can refuse to delete the account.

import { FetchFn } from "./supabase_rest.ts";
import { isObj, Json, st } from "./util.ts";

const STRIPE_API = "https://api.stripe.com/v1";
const DEAD_STATUSES = new Set(["canceled", "incomplete_expired"]);

async function raw(
  fetchFn: FetchFn,
  secretKey: string,
  method: "GET" | "DELETE",
  path: string,
  query: Record<string, string> = {},
  idempotencyKey = "",
): Promise<{ status: number; data: Json }> {
  const q = new URLSearchParams(query).toString();
  const headers: Record<string, string> = { Authorization: `Bearer ${secretKey}` };
  if (idempotencyKey) headers["Idempotency-Key"] = idempotencyKey;
  const res = await fetchFn(`${STRIPE_API}${path}${q ? `?${q}` : ""}`, { method, headers });
  const data = await res.json().catch(() => ({}));
  return { status: res.status, data: isObj(data) ? data : {} };
}

function missing(r: { status: number; data: Json }): boolean {
  return r.status === 404 || (r.status === 400 && isObj(r.data.error) && st(r.data.error.code) === "resource_missing");
}

/** Returns the ids it canceled. Throws on any Stripe failure other than "already gone". */
export async function cancelSubscriptionsForDeletion(
  fetchFn: FetchFn,
  secretKey: string,
  ids: { customerId: string; subscriptionId: string },
): Promise<string[]> {
  const candidates = new Set<string>();
  if (ids.subscriptionId) candidates.add(ids.subscriptionId);
  if (ids.customerId) {
    const list = await raw(fetchFn, secretKey, "GET", "/subscriptions", {
      customer: ids.customerId,
      status: "all",
      limit: "100",
    });
    if (list.status >= 400 && !missing(list)) throw new Error(`Stripe subscription list failed (${list.status})`);
    for (const s of Array.isArray(list.data.data) ? list.data.data : []) {
      if (isObj(s) && st(s.id) && !DEAD_STATUSES.has(st(s.status))) candidates.add(st(s.id));
    }
  }

  const canceled: string[] = [];
  for (const id of candidates) {
    const current = await raw(fetchFn, secretKey, "GET", `/subscriptions/${encodeURIComponent(id)}`);
    if (missing(current)) continue;
    if (current.status >= 400) throw new Error(`Stripe subscription lookup failed (${current.status})`);
    if (DEAD_STATUSES.has(st(current.data.status))) continue;
    const del = await raw(fetchFn, secretKey, "DELETE", `/subscriptions/${encodeURIComponent(id)}`, {}, `delete-account-cancel-${id}`);
    if (missing(del)) continue;
    if (del.status >= 400) throw new Error(`Stripe subscription cancel failed (${del.status})`);
    canceled.push(id);
  }
  return canceled;
}
