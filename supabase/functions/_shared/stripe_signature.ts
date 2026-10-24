// Stripe webhook signature verification (replaces stripe.Webhook.construct_event).
// Scheme: header `Stripe-Signature: t=<unix>,v1=<hex hmac>[,v1=...]`; the signed
// payload is `${t}.${rawBody}`, HMAC-SHA256 keyed with the endpoint secret.

import { timingSafeEqual } from "./util.ts";

export const DEFAULT_TOLERANCE_SECONDS = 300; // same as the stripe SDK default

export class SignatureError extends Error {}

async function hmacHex(secret: string, message: string): Promise<string> {
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const sig = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(message));
  return Array.from(new Uint8Array(sig)).map((b) => b.toString(16).padStart(2, "0")).join("");
}

/** Test/fixture helper: produce a valid header for a payload. */
export async function signStripePayload(secret: string, payload: string, timestamp: number): Promise<string> {
  return `t=${timestamp},v1=${await hmacHex(secret, `${timestamp}.${payload}`)}`;
}

/** Throws SignatureError unless the header is valid for the RAW body. Returns parsed JSON event. */
export async function verifyStripeSignature(
  rawBody: string,
  header: string,
  secret: string,
  opts: { nowSeconds?: number; toleranceSeconds?: number } = {},
): Promise<Record<string, unknown>> {
  if (!secret) throw new SignatureError("Stripe webhook secret is not configured.");
  let timestamp = "";
  const candidates: string[] = [];
  for (const part of header.split(",")) {
    const idx = part.indexOf("=");
    if (idx < 0) continue;
    const k = part.slice(0, idx).trim();
    const v = part.slice(idx + 1).trim();
    if (k === "t") timestamp = v;
    else if (k === "v1") candidates.push(v);
  }
  if (!/^\d+$/.test(timestamp) || candidates.length === 0) {
    throw new SignatureError("Invalid Stripe webhook signature.");
  }
  const expected = await hmacHex(secret, `${timestamp}.${rawBody}`);
  if (!candidates.some((c) => timingSafeEqual(c, expected))) {
    throw new SignatureError("Invalid Stripe webhook signature.");
  }
  const now = opts.nowSeconds ?? Math.floor(Date.now() / 1000);
  const tolerance = opts.toleranceSeconds ?? DEFAULT_TOLERANCE_SECONDS;
  if (tolerance > 0 && Math.abs(now - Number(timestamp)) > tolerance) {
    throw new SignatureError("Invalid Stripe webhook signature.");
  }
  try {
    const event = JSON.parse(rawBody);
    if (typeof event !== "object" || event === null || Array.isArray(event)) throw new Error();
    return event as Record<string, unknown>;
  } catch {
    throw new SignatureError("Invalid Stripe webhook signature.");
  }
}
