/**
 * Pure decision logic for converting a web guest (Supabase anonymous user)
 * into a permanent account WITHOUT changing the user id (parity with
 * mobile/src/lib/guestConversion.ts). No Supabase or DOM access here except
 * the optional Storage argument, so everything is unit-testable.
 */

export const RETURN_PATH_KEY = "fd_auth_return_path";
export const RETURN_PATH_TTL_MS = 60 * 60 * 1000;

/**
 * Returns a same-origin relative path ("/premium?x=1#y") or null. Rejects
 * absolute URLs, protocol-relative ("//evil"), backslash tricks, control
 * characters and anything that is not rooted at a single "/".
 */
export function safeReturnPath(raw: string | null | undefined): string | null {
  if (typeof raw !== "string") return null;
  const value = raw.trim();
  if (!value || value.length > 2000) return null;
  if (!value.startsWith("/")) return null;
  if (value.startsWith("//") || value.includes("\\")) return null;
  if (/[\u0000-\u001f\u007f]/.test(value)) return null;
  try {
    const parsed = new URL(value, "https://same-origin.invalid");
    if (parsed.origin !== "https://same-origin.invalid") return null;
    return parsed.pathname + parsed.search + parsed.hash;
  } catch {
    return null;
  }
}

export function canConvertGuest(session: { user?: { is_anonymous?: boolean | null } | null } | null | undefined): boolean {
  return Boolean(session?.user?.is_anonymous);
}

interface ErrorLike {
  code?: string | null;
  message?: string | null;
  status?: number | null;
}

export type GuestUpgradeFailure = "email-exists" | "link-unavailable" | "identity-exists" | "other";

/**
 * Maps a Supabase auth error from updateUser/linkIdentity to what the UI
 * should do. "link-unavailable" means the project has manual linking
 * disabled (Dashboard > Authentication > Sign In / Providers > "Allow manual
 * linking"); the caller falls back to a plain sign-in only after telling the
 * user their guest data will not be carried over.
 */
export function classifyUpgradeError(err: ErrorLike | null | undefined): GuestUpgradeFailure {
  if (!err) return "other";
  const code = err.code ?? "";
  const message = (err.message ?? "").toLowerCase();
  if (code === "manual_linking_disabled" || message.includes("manual linking is disabled")) return "link-unavailable";
  if (code === "identity_already_exists" || message.includes("identity is already linked")) return "identity-exists";
  if (
    code === "email_exists" ||
    code === "user_already_exists" ||
    message.includes("already been registered") ||
    message.includes("already registered") ||
    message.includes("email address has already")
  ) {
    return "email-exists";
  }
  return "other";
}

export type EmailUpgradeOutcome = "converted" | "confirm-email";

/**
 * After updateUser({email, password}) on an anonymous session: with email
 * auto-confirm the user is permanent immediately; otherwise Supabase keeps
 * the user anonymous with `new_email` pending until the link is clicked.
 */
export function classifyEmailUpgradeResult(
  user: { is_anonymous?: boolean | null; email?: string | null } | null | undefined,
  email: string,
): EmailUpgradeOutcome {
  if (user && user.is_anonymous === false && (user.email ?? "").toLowerCase() === email.trim().toLowerCase()) {
    return "converted";
  }
  return "confirm-email";
}

export const GUEST_DATA_NOT_MERGED_NOTICE =
  "That email already has an account. Signing in will not carry over what you did as a guest.";

export const LINK_UNAVAILABLE_NOTICE =
  "We couldn't link this sign-in to your guest session. You can continue, but your guest data will not be carried over.";

export const IDENTITY_EXISTS_NOTICE =
  "That account already exists. Signing in with it will not carry over what you did as a guest.";

interface StoredReturn {
  path: string;
  at: number;
}

export function storeReturnPath(storage: Pick<Storage, "setItem"> | null | undefined, raw: string, now = Date.now()): void {
  const path = safeReturnPath(raw);
  if (!storage || !path) return;
  try {
    storage.setItem(RETURN_PATH_KEY, JSON.stringify({ path, at: now } satisfies StoredReturn));
  } catch {
    /* storage unavailable */
  }
}

/** Reads (and re-validates) a stored return path; null if missing, stale or unsafe. */
export function readReturnPath(storage: Pick<Storage, "getItem"> | null | undefined, now = Date.now()): string | null {
  if (!storage) return null;
  try {
    const raw = storage.getItem(RETURN_PATH_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<StoredReturn>;
    if (typeof parsed.at !== "number" || now - parsed.at > RETURN_PATH_TTL_MS || now < parsed.at) return null;
    return safeReturnPath(parsed.path);
  } catch {
    return null;
  }
}

export function clearReturnPath(storage: Pick<Storage, "removeItem"> | null | undefined): void {
  try {
    storage?.removeItem(RETURN_PATH_KEY);
  } catch {
    /* ignore */
  }
}

/** Extracts an auth error Supabase appended to the callback URL (query or hash). */
export function parseAuthCallbackError(search: string, hash: string): { code: string | null; description: string } | null {
  const params = new URLSearchParams(`${search.replace(/^\?/, "")}&${hash.replace(/^#/, "")}`);
  const code = params.get("error_code");
  const err = params.get("error");
  if (!code && !err) return null;
  return { code, description: params.get("error_description") ?? err ?? "" };
}

/**
 * Should the post-auth redirect to the stored path fire now? Only for a real
 * (non-anonymous) session, and never when already on that path.
 */
export function shouldRestoreReturnPath(args: {
  stored: string | null;
  isAnonymous: boolean;
  hasSession: boolean;
  currentPath: string;
}): boolean {
  if (!args.stored || !args.hasSession || args.isAnonymous) return false;
  return args.stored !== args.currentPath;
}
