"use client";

import { useState } from "react";

import { useAuth } from "@/context/AuthContext";
import { AgeGate } from "./AgeGate";

/**
 * Ports modules/account_ui.py's render_mobile_auth_entry sign-in/create-
 * account forms (email + password, "New here? Create account" toggle),
 * using Supabase JS directly like mobile/src/context/AuthContext.tsx does
 * — not Streamlit's raw-requests-against-GoTrue approach (that plumbing
 * only exists because Streamlit has no browser localStorage access; see
 * auth research notes). Create-account is age-gated, matching
 * modules/guest_conversion.py's signup dialog; sign-in is not (an
 * existing account already passed the gate at signup).
 *
 * `signUp` succeeding is not the same thing as being signed in — this
 * project requires email confirmation, so a successful signUp call returns
 * no error but also creates no session (mirrors mobile's LoginScreen.tsx,
 * the reference this form was ported from: it never calls its own
 * "proceed" step off a signUp result either, only ever off signIn).
 * Calling onSignedIn() unconditionally here meant a brand-new account
 * fell straight through to SleeperImportForm with useAuth().session still
 * null, which silently created a disposable anonymous guest session
 * instead (SleeperImportForm's own `if (!session) signInAsGuest()` guard,
 * written for the deliberate "Try without an account" tab) — the user
 * believed they'd created a real account and continued the flow, but
 * every league they saved belonged to that throwaway anonymous identity,
 * never to the unconfirmed email+password account sitting in Supabase
 * waiting for a confirmation click that was never going to come.
 */
export function SignInForm({ onSignedIn }: { onSignedIn: () => void }) {
  const { signIn, signUp } = useAuth();
  const [mode, setMode] = useState<"sign-in" | "create-account">("sign-in");
  const [ageConfirmed, setAgeConfirmed] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setNotice(null);
    const result = mode === "sign-in" ? await signIn(email, password) : await signUp(email, password);
    setBusy(false);
    if (result.error) {
      setError(result.error);
      return;
    }
    if (mode === "create-account") {
      setNotice("Check your email to confirm your account, then sign in.");
      setMode("sign-in");
      setAgeConfirmed(false);
      return;
    }
    onSignedIn();
  };

  return (
    <div className="flex flex-col gap-4">
      <form onSubmit={handleSubmit} className="flex flex-col gap-3">
        <label className="flex flex-col gap-1 text-sm">
          Email
          <input
            type="email"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            className="px-3 py-2"
            style={{
              background: "var(--color-surface-secondary)",
              color: "var(--color-text-primary)",
              border: "var(--border-width-default) solid var(--color-border)",
            }}
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          Password
          <input
            type="password"
            required
            minLength={6}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            className="px-3 py-2"
            style={{
              background: "var(--color-surface-secondary)",
              color: "var(--color-text-primary)",
              border: "var(--border-width-default) solid var(--color-border)",
            }}
          />
        </label>

        {mode === "create-account" && !ageConfirmed ? (
          <AgeGate onConfirmed={() => setAgeConfirmed(true)} />
        ) : (
          <>
            {error ? (
              <p role="alert" className="text-xs" style={{ color: "var(--color-danger)" }}>
                {error}
              </p>
            ) : null}
            {notice ? (
              <p className="text-xs" style={{ color: "var(--color-success)" }}>
                {notice}
              </p>
            ) : null}
            <button
              type="submit"
              disabled={busy}
              className="px-4 py-2 text-sm font-bold self-start"
              style={{
                background: "var(--color-accent-strong)",
                color: "var(--color-brand-mark-ink)",
                fontWeight: "var(--font-weight-button)",
                opacity: busy ? "var(--opacity-disabled)" : 1,
              }}
            >
              {mode === "sign-in" ? "Sign in" : "Create account"}
            </button>
          </>
        )}
      </form>

      <button
        type="button"
        onClick={() => {
          setMode(mode === "sign-in" ? "create-account" : "sign-in");
          setAgeConfirmed(false);
          setError(null);
          setNotice(null);
        }}
        className="text-xs underline self-start"
        style={{ color: "var(--color-text-muted)" }}
      >
        {mode === "sign-in" ? "New here? Create account" : "Already have an account? Sign in"}
      </button>
    </div>
  );
}
