/**
 * Account deletion, server side. Deleting an account must cancel its Stripe
 * subscription first, which only a server can do, so both clients call the
 * `delete-account` Supabase Edge Function (supabase/functions/delete-account)
 * instead of the `delete_user` RPC directly. The function cancels, and only
 * if that succeeds deletes; on failure it returns an error and deletes
 * nothing, which we surface instead of signing the user out.
 *
 * Web and mobile share this file byte-for-byte (mobile/src/lib/
 * accountDeletion.ts); a web test keeps them in sync.
 */

/** Shown in the delete confirmation on every surface. */
export const DELETE_ACCOUNT_BILLING_NOTE =
  "Deleting your account also cancels a subscription bought on the web. Subscriptions bought in the App Store or Google Play must be canceled in the store.";

export const DELETE_ACCOUNT_FALLBACK_ERROR =
  "Could not delete your account, and nothing was deleted. Please try again.";

interface InvokeResult {
  data: unknown;
  error: { message?: string; context?: unknown } | null;
}

export interface FunctionsInvoker {
  functions: {
    invoke: (name: string, options?: { method?: "POST"; body?: Record<string, unknown> }) => Promise<InvokeResult>;
  };
}

async function serverMessage(error: { message?: string; context?: unknown }): Promise<string> {
  const context = error.context as { json?: () => Promise<unknown> } | undefined;
  if (context && typeof context.json === "function") {
    try {
      const body = (await context.json()) as { error?: unknown } | null;
      if (body && typeof body.error === "string" && body.error.trim()) return body.error.trim();
    } catch {
      /* fall through */
    }
  }
  return DELETE_ACCOUNT_FALLBACK_ERROR;
}

/** Cancel billing then delete. `error` is null only when the account is gone. */
export async function deleteAccountOnServer(client: FunctionsInvoker): Promise<{ error: string | null }> {
  try {
    const { data, error } = await client.functions.invoke("delete-account", { method: "POST", body: {} });
    if (error) return { error: await serverMessage(error) };
    if (!data || (data as { ok?: unknown }).ok !== true) return { error: DELETE_ACCOUNT_FALLBACK_ERROR };
    return { error: null };
  } catch {
    return { error: DELETE_ACCOUNT_FALLBACK_ERROR };
  }
}
