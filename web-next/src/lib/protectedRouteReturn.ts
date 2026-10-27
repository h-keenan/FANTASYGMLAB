/**
 * "Remember where a signed-out visitor was headed, then send them back
 * after they sign in" for routes that require a session (/premium,
 * /connect-league). P0 UX audit, 2026-10-27: both pages used to silently
 * `router.replace("/")` a logged-out visitor with no way back -- clicking a
 * shared /premium link, or the league switcher's "+ Add another league"
 * link while signed out, meant losing that destination entirely once
 * signed in.
 *
 * Deliberately a SEPARATE storage key and mechanism from lib/guestUpgrade.ts's
 * return-path (RETURN_PATH_KEY / storeReturnPath / shouldRestoreReturnPath):
 * that one is restored globally, in AuthContext, the instant ANY real
 * session appears -- correct for its own use (an OAuth/email-link round
 * trip that already has an account). Reusing it here would also fire for a
 * brand-new signup's first real session, which happens as soon as signUp()
 * resolves -- well before the mandatory onboarding carousel -> paywall
 * sequence (LandingAuthIsland) has run, hard-navigating a fresh account
 * straight past both. This return path is instead read and consumed only
 * from LandingAuthIsland's existing-saved-leagues branch (see its own
 * comment), which by construction only ever runs for an account that
 * already has 1+ saved leagues -- never a brand-new signup.
 */

const PROTECTED_RETURN_PATH_KEY = "fd_protected_route_return_path";
const PROTECTED_RETURN_PATH_TTL_MS = 60 * 60 * 1000;

interface StoredProtectedReturn {
  path: string;
  at: number;
}

/** Returns a same-origin relative path ("/premium?x=1#y") or null. Mirrors
 * lib/guestUpgrade.ts's safeReturnPath exactly (kept duplicated rather than
 * imported/shared so this module has zero dependency on the guest-upgrade
 * feature's own evolution). Rejects absolute URLs, protocol-relative
 * ("//evil"), backslash tricks, control characters and anything not rooted
 * at a single "/". */
export function safeProtectedPath(raw: string | null | undefined): string | null {
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

export function storeProtectedReturnPath(
  storage: Pick<Storage, "setItem"> | null | undefined,
  raw: string,
  now = Date.now(),
): void {
  const path = safeProtectedPath(raw);
  if (!storage || !path) return;
  try {
    storage.setItem(PROTECTED_RETURN_PATH_KEY, JSON.stringify({ path, at: now } satisfies StoredProtectedReturn));
  } catch {
    /* storage unavailable */
  }
}

/** Reads (and re-validates) a stored protected-route return path; null if
 * missing, stale or unsafe. Does not clear it -- call clearProtectedReturnPath
 * once the caller has actually used (or deliberately ignored) the value. */
export function readProtectedReturnPath(storage: Pick<Storage, "getItem"> | null | undefined, now = Date.now()): string | null {
  if (!storage) return null;
  try {
    const raw = storage.getItem(PROTECTED_RETURN_PATH_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<StoredProtectedReturn>;
    if (typeof parsed.at !== "number" || now - parsed.at > PROTECTED_RETURN_PATH_TTL_MS || now < parsed.at) return null;
    return safeProtectedPath(parsed.path);
  } catch {
    return null;
  }
}

export function clearProtectedReturnPath(storage: Pick<Storage, "removeItem"> | null | undefined): void {
  try {
    storage?.removeItem(PROTECTED_RETURN_PATH_KEY);
  } catch {
    /* ignore */
  }
}

function safeLocalStorage(): Storage | null {
  try {
    return typeof window === "undefined" ? null : window.localStorage;
  } catch {
    return null;
  }
}

/** Stores the current path (path + search + hash) so a protected page's
 * sign-out redirect can be undone later. No-op outside the browser. */
export function storeCurrentPathForReturnAfterSignIn(): void {
  if (typeof window === "undefined") return;
  storeProtectedReturnPath(safeLocalStorage(), window.location.pathname + window.location.search + window.location.hash);
}

/** Convenience pair for LandingAuthIsland's existing-user branch: read once,
 * then always clear (whether or not the caller ends up using the value) so
 * a stale entry never redirects a later, unrelated sign-in. */
export function consumeProtectedReturnPath(): string | null {
  const storage = safeLocalStorage();
  const path = readProtectedReturnPath(storage);
  clearProtectedReturnPath(storage);
  return path;
}
