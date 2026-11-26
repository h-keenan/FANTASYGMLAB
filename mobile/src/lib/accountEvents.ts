/**
 * Mobile counterpart of web-next/src/lib/signupTracking.ts (deliberately a differently named file: AsyncStorage is async, so the code is not a byte-for-byte lib twin): report a brand-new registered account (email / Google / Apple)
 * or a new guest session exactly once per account, so signup_completed and guest_session_started cover every sign-up
 * path (previously the app emitted neither). Pure (no React Native imports) so it runs under `node --test`.
 * Only signup_method (email | google | apple | other) leaves the device, never an email, name or provider id.
 */

export type SignupMethod = 'email' | 'google' | 'apple' | 'other';

export interface SignupUser {
  id?: string;
  is_anonymous?: boolean;
  created_at?: string;
  email_confirmed_at?: string | null;
  app_metadata?: { provider?: string; providers?: string[] } | null;
  identities?: Array<{ provider?: string }> | null;
}

export interface MarkerStorage {
  getItem(key: string): Promise<string | null>;
  setItem(key: string, value: string): Promise<void>;
}

export const RECENT_MS = 15 * 60 * 1000;
const DONE = 'fd_acct_event_v1:';
const GUEST = 'fd_guest_seen_v1:';

export function signupMethodOf(user: SignupUser): SignupMethod {
  const candidates = [
    ...(user.identities ?? []).map((i) => i.provider),
    user.app_metadata?.provider,
    ...(user.app_metadata?.providers ?? []),
  ];
  for (const raw of candidates) {
    const p = String(raw ?? '').toLowerCase();
    if (p === 'google' || p === 'apple' || p === 'email') return p;
  }
  return 'other';
}

function recent(iso: string | null | undefined, nowMs: number): boolean {
  if (!iso) return false;
  const t = Date.parse(iso);
  return Number.isFinite(t) && nowMs - t >= -60_000 && nowMs - t <= RECENT_MS;
}

export type AccountEvent =
  | { event: 'signup_completed'; method: SignupMethod }
  | { event: 'guest_session_started' };

export async function detectAccountEvent(
  user: SignupUser | null | undefined,
  storage: MarkerStorage,
  nowMs: number = Date.now(),
): Promise<AccountEvent | null> {
  const id = String(user?.id ?? '');
  if (!user || !id) return null;
  try {
    if (user.is_anonymous) {
      if (await storage.getItem(GUEST + id)) return null;
      await storage.setItem(GUEST + id, '1');
      return recent(user.created_at, nowMs) ? { event: 'guest_session_started' } : null;
    }
    if (await storage.getItem(DONE + id)) return null;
    const method = signupMethodOf(user);
    const wasGuest = Boolean(await storage.getItem(GUEST + id));
    const isNew =
      wasGuest || recent(user.created_at, nowMs) || (method === 'email' && recent(user.email_confirmed_at, nowMs));
    if (!isNew) return null;
    await storage.setItem(DONE + id, '1');
    return { event: 'signup_completed', method };
  } catch {
    return null;
  }
}
