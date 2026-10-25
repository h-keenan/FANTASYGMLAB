// Small helpers shared by every billing function. No Deno globals here so the
// same code runs under `deno test` and (for local verification) `bun test`.

export type Json = Record<string, unknown>;

/** Port of Python `_safe_text`: None -> "", else str(value).strip(). */
export function st(value: unknown): string {
  return value === null || value === undefined ? "" : String(value).trim();
}

export function isObj(value: unknown): value is Json {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/** Python `int(x)` for the shapes Stripe/RevenueCat send; null when invalid. */
export function pyInt(value: unknown): number | null {
  if (value === null || value === undefined || typeof value === "boolean") return null;
  if (typeof value === "number") return Number.isFinite(value) ? Math.trunc(value) : null;
  if (typeof value === "string") {
    return /^\s*[+-]?\d+\s*$/.test(value) ? Number(value.trim()) : null;
  }
  return null;
}

/** Positive epoch seconds or null (port of `_epoch`). */
export function epoch(value: unknown): number | null {
  const n = pyInt(value);
  return n !== null && n > 0 ? n : null;
}

export function isoFromEpoch(value: number | null): string {
  return value === null ? "" : new Date(value * 1000).toISOString();
}

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
export function isUuid(value: string): boolean {
  return UUID_RE.test(value);
}

/** Constant-time string compare (port of hmac.compare_digest). */
export function timingSafeEqual(a: string, b: string): boolean {
  const enc = new TextEncoder();
  const x = enc.encode(a);
  const y = enc.encode(b);
  let diff = x.length ^ y.length;
  const len = Math.max(x.length, y.length);
  for (let i = 0; i < len; i++) diff |= (x[i] ?? 0) ^ (y[i] ?? 0);
  return diff === 0;
}

export function jsonResponse(body: unknown, status = 200, extra: HeadersInit = {}): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...extra },
  });
}

export function errorResponse(status: number, error: string, extra: HeadersInit = {}, code?: string): Response {
  return jsonResponse(code ? { ok: false, error, code } : { ok: false, error }, status, extra);
}

/** Thrown with an HTTP status; message is client-safe. */
export class HttpError extends Error {
  status: number;
  code?: string;
  constructor(status: number, message: string, code?: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

export type Env = (name: string) => string | undefined;

export function envValue(env: Env, name: string): string {
  return st(env(name));
}

/** Stable machine code + copy for "guests may not buy" (create-checkout-session). */
export const ACCOUNT_REQUIRED_CODE = "account_required";
export const ACCOUNT_REQUIRED_MESSAGE = "Create an account to start your free trial.";
