/**
 * Server-side account deletion client. The `delete-account` edge function
 * cancels any Stripe subscription first, revokes the Sign in with Apple grant
 * (when the project has APPLE_* secrets), then deletes the user; it refuses
 * (user NOT deleted) if billing cannot be cancelled.
 *
 * Pure (injected fetch / Apple code getter) so it is unit-testable under
 * `node --test` without React Native.
 */

export interface AccountDeletionDeps {
  supabaseUrl: string;
  anonKey: string;
  accessToken: string;
  fetchFn: (url: string, init: { method: string; headers: Record<string, string>; body: string }) => Promise<{
    ok: boolean;
    status: number;
    json: () => Promise<unknown>;
  }>;
  /** Re-authenticates with Apple and returns a fresh single-use authorizationCode, or null. */
  getAppleAuthorizationCode?: () => Promise<string | null>;
}

export interface AccountDeletionResult {
  error: string | null;
}

export async function requestAccountDeletion(deps: AccountDeletionDeps): Promise<AccountDeletionResult> {
  let appleCode: string | null = null;
  if (deps.getAppleAuthorizationCode) {
    try {
      appleCode = await deps.getAppleAuthorizationCode();
    } catch {
      appleCode = null; // cancelled/unavailable: deletion proceeds; revocation is skipped
    }
  }
  let res;
  try {
    res = await deps.fetchFn(`${deps.supabaseUrl.replace(/\/+$/, '')}/functions/v1/delete-account`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${deps.accessToken}`,
        apikey: deps.anonKey,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(appleCode ? { apple_authorization_code: appleCode } : {}),
    });
  } catch {
    return { error: 'Could not reach the server. Check your connection and try again.' };
  }
  if (res.ok) return { error: null };
  let message = '';
  try {
    const body = (await res.json()) as { error?: unknown } | null;
    if (body && typeof body.error === 'string') message = body.error;
  } catch {
    // non-JSON error body
  }
  return { error: message || `Could not delete the account (status ${res.status}).` };
}

/** True when the Supabase user signed in with Apple (so a revocation code is worth requesting). */
export function hasAppleIdentity(user: { identities?: { provider?: string }[] | null } | null | undefined): boolean {
  return Boolean(user?.identities?.some((i) => i.provider === 'apple'));
}
