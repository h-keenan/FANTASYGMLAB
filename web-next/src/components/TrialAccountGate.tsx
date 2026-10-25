"use client";

import { useState } from "react";

import { Button } from "@/components/Button";
import { SignInForm } from "@/components/SignInForm";
import { ApiError } from "@/lib/api";

/** Stable machine code returned by the create-checkout-session Edge Function for guests. */
export const ACCOUNT_REQUIRED_CODE = "account_required";

export const ACCOUNT_REQUIRED_MESSAGE = "Create an account to start your free trial.";

/** True when a checkout call was refused because the caller is a guest (anonymous) session. */
export function isAccountRequiredError(err: unknown): boolean {
  return err instanceof ApiError && (err.code === ACCOUNT_REQUIRED_CODE || (err.status === 403 && err.message === ACCOUNT_REQUIRED_MESSAGE));
}

/**
 * Replaces the "Start trial" / "Subscribe" button for guest (anonymous)
 * sessions. Guests may not buy: a purchase would attach to a throwaway user
 * id. Reveals the existing sign-in / create-account form (email, Google,
 * Apple) in place; on email success the caller's session is a real account,
 * `isGuest` flips to false and the paywall shows its normal button again, so
 * the user is already back where they were. Google/Apple redirect away
 * through the existing OAuth flow (unchanged).
 */
export function TrialAccountGate({ onSignedIn }: { onSignedIn?: () => void }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="flex flex-col gap-2" data-testid="trial-account-gate">
      <p role="status" className="text-sm font-bold">
        {ACCOUNT_REQUIRED_MESSAGE}
      </p>
      {open ? (
        <div className="fd-landing-dark rounded-xl p-3">
          <SignInForm onSignedIn={() => onSignedIn?.()} />
        </div>
      ) : (
        <Button variant="premium" type="button" onClick={() => setOpen(true)} style={{ alignSelf: "auto" }}>
          Create account
        </Button>
      )}
    </div>
  );
}
