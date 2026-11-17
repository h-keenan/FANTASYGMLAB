// Account-deletion side effects that must run BEFORE the auth user is removed:
//   1. cancel every live Stripe subscription (so a deleted user is never billed)
//   2. revoke the user's Sign in with Apple grant (App Store Guideline 5.1.1(v))
// Both are injectable-fetch, secret-free, and idempotent. See docs/account-deletion.md.

import { StripeConfig, secretModeConfigured } from "./config.ts";
import { stripeRequest, StripeHttpError } from "./stripe_api.ts";
import { FetchFn } from "./supabase_rest.ts";
import { Env, envValue, HttpError, isObj, Json, st } from "./util.ts";

/** Subscription states that can still produce an invoice. Everything else is already terminal. */
const TERMINAL_STATUSES = new Set(["canceled", "incomplete_expired"]);

export interface StripeCancelResult {
  /** Subscription ids that were live and are now canceled by this call. */
  canceled: string[];
  /** Ids that were already terminal / already gone (idempotent re-run). */
  alreadyGone: string[];
}

function subscriptionRows(data: Json): Json[] {
  return Array.isArray(data.data) ? data.data.filter(isObj) : [];
}

/**
 * Cancel every live subscription for this customer (plus the profile's known
 * subscription id and any subscription tagged with the user's id in metadata).
 * Throws on any Stripe failure other than "already gone": the caller must then
 * abort the deletion so the user is not left deleted-but-billed.
 */
export async function cancelUserSubscriptions(
  fetchFn: FetchFn,
  config: StripeConfig,
  ids: { userId: string; customerId: string; subscriptionId: string },
): Promise<StripeCancelResult> {
  const result: StripeCancelResult = { canceled: [], alreadyGone: [] };
  const hasStripeState = !!(ids.customerId || ids.subscriptionId);
  if (!secretModeConfigured(config)) {
    if (hasStripeState) throw new HttpError(503, "Billing is temporarily unavailable, so the account cannot be deleted yet. Please try again shortly.", "billing_unavailable");
    return result; // nothing in Stripe to cancel and Stripe is not configured
  }

  const live = new Map<string, string>(); // subscription id -> status
  if (ids.customerId) {
    const list = await stripeRequest(fetchFn, config.secretKey, "GET", "/subscriptions", {
      customer: ids.customerId,
      status: "all",
      limit: 100,
    });
    for (const sub of subscriptionRows(list)) live.set(st(sub.id), st(sub.status).toLowerCase());
  }
  if (ids.subscriptionId && !live.has(ids.subscriptionId)) live.set(ids.subscriptionId, "unknown");

  // Safety net for a checkout whose webhook has not yet written the profile ids.
  // Best-effort only: search is eventually consistent and may be unavailable.
  try {
    const found = await stripeRequest(fetchFn, config.secretKey, "GET", "/subscriptions/search", {
      query: `metadata['supabase_user_id']:'${ids.userId.replace(/'/g, "")}'`,
      limit: 100,
    });
    for (const sub of subscriptionRows(found)) if (!live.has(st(sub.id))) live.set(st(sub.id), st(sub.status).toLowerCase());
  } catch (e) {
    console.error("delete-account: subscription search failed (non-fatal)", (e as Error).message);
  }

  for (const [subId, status] of live) {
    if (!subId) continue;
    if (TERMINAL_STATUSES.has(status)) {
      result.alreadyGone.push(subId);
      continue;
    }
    try {
      await stripeRequest(fetchFn, config.secretKey, "DELETE", `/subscriptions/${encodeURIComponent(subId)}`, {
        invoice_now: "false",
        prorate: "false",
      });
      result.canceled.push(subId);
    } catch (e) {
      // Already canceled / deleted between list and cancel (e.g. webhook race, retry).
      if (e instanceof StripeHttpError && (e.status === 404 || e.stripeCode === "resource_missing")) {
        result.alreadyGone.push(subId);
        continue;
      }
      throw e;
    }
  }
  return result;
}

// ---- Sign in with Apple token revocation ----

export interface AppleConfig {
  teamId: string;
  keyId: string;
  /** PEM contents of the .p8 key. Literal "\n" sequences are accepted (env-var friendly). */
  privateKey: string;
  /** Bundle id for native sign-in (com.fantasygmlab.app) or the Services ID for web. */
  clientId: string;
}

export function loadAppleConfig(env: Env): AppleConfig | null {
  const cfg = {
    teamId: envValue(env, "APPLE_TEAM_ID"),
    keyId: envValue(env, "APPLE_KEY_ID"),
    privateKey: envValue(env, "APPLE_PRIVATE_KEY").replace(/\\n/g, "\n"),
    clientId: envValue(env, "APPLE_CLIENT_ID"),
  };
  return cfg.teamId && cfg.keyId && cfg.privateKey && cfg.clientId ? cfg : null;
}

function b64url(bytes: Uint8Array | string): string {
  const raw = typeof bytes === "string" ? new TextEncoder().encode(bytes) : bytes;
  let bin = "";
  for (const b of raw) bin += String.fromCharCode(b);
  return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

/** ES256 client-secret JWT Apple requires for /auth/token and /auth/revoke (max 6 months; we mint per call). */
export async function appleClientSecret(cfg: AppleConfig, nowSeconds: number): Promise<string> {
  const pem = cfg.privateKey.replace(/-----(BEGIN|END) PRIVATE KEY-----/g, "").replace(/\s+/g, "");
  const der = Uint8Array.from(atob(pem), (c) => c.charCodeAt(0));
  const key = await crypto.subtle.importKey("pkcs8", der, { name: "ECDSA", namedCurve: "P-256" }, false, ["sign"]);
  const header = b64url(JSON.stringify({ alg: "ES256", kid: cfg.keyId, typ: "JWT" }));
  const payload = b64url(JSON.stringify({
    iss: cfg.teamId,
    iat: nowSeconds,
    exp: nowSeconds + 300,
    aud: "https://appleid.apple.com",
    sub: cfg.clientId,
  }));
  const signingInput = `${header}.${payload}`;
  // WebCrypto ECDSA output is already the raw r||s form JWT ES256 requires.
  const sig = new Uint8Array(await crypto.subtle.sign({ name: "ECDSA", hash: "SHA-256" }, key, new TextEncoder().encode(signingInput)));
  return `${signingInput}.${b64url(sig)}`;
}

async function appleForm(fetchFn: FetchFn, url: string, form: Record<string, string>): Promise<Response> {
  return await fetchFn(url, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams(form).toString(),
  });
}

/**
 * Exchange the fresh authorizationCode (collected by re-authenticating with Apple
 * at deletion time) for a refresh token, then revoke it. Apple authorization codes
 * are single-use and expire in 5 minutes, which is why this happens at deletion.
 * Returns true when Apple confirmed revocation.
 */
export async function revokeAppleGrant(
  fetchFn: FetchFn,
  cfg: AppleConfig,
  authorizationCode: string,
  nowSeconds: number,
): Promise<boolean> {
  const clientSecret = await appleClientSecret(cfg, nowSeconds);
  const tokenRes = await appleForm(fetchFn, "https://appleid.apple.com/auth/token", {
    client_id: cfg.clientId,
    client_secret: clientSecret,
    code: authorizationCode,
    grant_type: "authorization_code",
  });
  if (tokenRes.status >= 400) return false;
  const tokens = await tokenRes.json().catch(() => ({}));
  const refresh = isObj(tokens) ? st(tokens.refresh_token) : "";
  const access = isObj(tokens) ? st(tokens.access_token) : "";
  const [token, hint] = refresh ? [refresh, "refresh_token"] : [access, "access_token"];
  if (!token) return false;
  const revokeRes = await appleForm(fetchFn, "https://appleid.apple.com/auth/revoke", {
    client_id: cfg.clientId,
    client_secret: clientSecret,
    token,
    token_type_hint: hint,
  });
  return revokeRes.status < 400;
}
