"use client";

import { useState } from "react";

import { useAuth } from "@/context/AuthContext";
import { AgeGate } from "./AgeGate";

const GLASS_CARD_STYLE: React.CSSProperties = {
  background: "rgba(255, 255, 255, 0.045)",
  backdropFilter: "blur(22px) saturate(160%)",
  WebkitBackdropFilter: "blur(22px) saturate(160%)",
  border: "1px solid rgba(255, 255, 255, 0.09)",
  boxShadow: "inset 0 1px 0 rgba(255, 255, 255, 0.08), 0 12px 36px rgba(0, 0, 0, 0.45)",
  borderRadius: "22px",
};

const FIELD_STYLE: React.CSSProperties = {
  background: "rgba(255, 255, 255, 0.06)",
  color: "var(--color-text-primary)",
  border: "1px solid rgba(255, 255, 255, 0.12)",
  borderRadius: "12px",
};

/**
 * Ports modules/account_ui.py's render_mobile_auth_entry sign-in/create-
 * account forms, using Supabase JS directly like mobile/src/context/
 * AuthContext.tsx does. Every signIn/signUp call and the email-confirm
 * handling below is unchanged from the original single-step version — only
 * the UI flow and visual treatment changed.
 *
 * Rebuilt 2026-10-18 (coridian_: "Redo the entire auth create account
 * page. It sucks rn. Just an email to get started" — sent right after the
 * day's one real, severe bug: an unrelated background layer silently
 * blocking every click on this exact page). Step 1 asks for only an
 * email, matching that instruction literally; step 2 (password, the age
 * gate for a new account, and the sign-in/create-account toggle) is
 * exactly the previous single-step form's own content, just gated behind
 * having entered an email first — no new auth capability, no guessing
 * whether an email already has an account (Supabase's client SDK has no
 * safe way to check that before an actual attempt), just a cleaner
 * sequence through the same calls. Glass-card treatment matches
 * OnboardingCarousel's already-approved liquid-glass language (this form
 * only ever renders inside the landing page's forced-dark .fd-landing-dark
 * wrapper, so the dark-only glass tokens are always correct here).
 *
 * `signUp` succeeding is not automatically the same thing as being signed
 * in: when the Supabase project requires email confirmation, a successful
 * signUp call returns no error but also creates no session yet. This
 * project currently has email auto-confirm ON (signUp returns an active
 * session immediately), so `AuthContext.signUp`'s `signedIn` flag is
 * checked here rather than assumed either way — covers both configurations
 * without guessing. Calling onSignedIn() when no session actually exists
 * would fall through to SleeperImportForm with useAuth().session still
 * null, which silently creates a disposable anonymous guest session
 * instead (SleeperImportForm's own `if (!session) signInAsGuest()` guard,
 * written for the deliberate "Try without an account" tab) — the user
 * would believe they'd created a real account and continued the flow, but
 * every league they saved would belong to that throwaway anonymous
 * identity, never to the email+password account actually sitting in
 * Supabase.
 */
export function SignInForm({ onSignedIn }: { onSignedIn: () => void }) {
  const { signIn, signUp } = useAuth();
  const [step, setStep] = useState<"email" | "password" | "check-email">("email");
  const [mode, setMode] = useState<"sign-in" | "create-account">("sign-in");
  const [ageConfirmed, setAgeConfirmed] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const handleEmailContinue = (event: React.FormEvent) => {
    event.preventDefault();
    if (!email) return;
    setStep("password");
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    const result = mode === "sign-in" ? await signIn(email, password) : await signUp(email, password);
    setBusy(false);
    if (result.error) {
      setError(result.error);
      return;
    }
    if (mode === "create-account" && !("signedIn" in result && result.signedIn)) {
      // coridian_, 2026-10-18: "I create an account. It doesn't say
      // anything. It takes me back to the default sign-in page..." — a
      // small text notice folded back into the sign-in form (now gone)
      // was too easy to miss, especially for the one outcome a new user
      // most needs to actually notice. A full dedicated screen can't be
      // scrolled past unread.
      setStep("check-email");
      return;
    }
    onSignedIn();
  };

  if (step === "check-email") {
    return (
      <div className="flex flex-col gap-4 p-6 text-center items-center" style={GLASS_CARD_STYLE}>
        <h2 className="text-lg font-extrabold" style={{ color: "var(--color-text-primary)" }}>
          Check your email
        </h2>
        <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
          We sent a confirmation link to <strong style={{ color: "var(--color-text-primary)" }}>{email}</strong>.
          Confirm your account, then come back here to sign in.
        </p>
        <button
          type="button"
          onClick={() => {
            setStep("password");
            setMode("sign-in");
            setAgeConfirmed(false);
            setError(null);
          }}
          className="px-4 py-2.5 text-sm font-bold"
          style={{
            background: "var(--color-accent-strong)",
            color: "var(--color-brand-mark-ink)",
            fontWeight: "var(--font-weight-button)",
            borderRadius: "12px",
          }}
        >
          Back to sign in
        </button>
      </div>
    );
  }

  if (step === "email") {
    return (
      <form onSubmit={handleEmailContinue} className="flex flex-col gap-4 p-6" style={GLASS_CARD_STYLE}>
        <div className="flex flex-col gap-1">
          <h2 className="text-lg font-extrabold" style={{ color: "var(--color-text-primary)" }}>
            Get started
          </h2>
          <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
            Enter your email to sign in or create an account.
          </p>
        </div>
        <label className="flex flex-col gap-1 text-sm" style={{ color: "var(--color-text-secondary)" }}>
          Email
          <input
            type="email"
            required
            autoFocus
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            className="px-3 py-2.5"
            style={FIELD_STYLE}
          />
        </label>
        <button
          type="submit"
          className="px-4 py-2.5 text-sm font-bold"
          style={{
            background: "var(--color-accent-strong)",
            color: "var(--color-brand-mark-ink)",
            fontWeight: "var(--font-weight-button)",
            borderRadius: "12px",
          }}
        >
          Continue
        </button>
      </form>
    );
  }

  return (
    <div className="flex flex-col gap-4 p-6" style={GLASS_CARD_STYLE}>
      <button
        type="button"
        onClick={() => {
          setStep("email");
          setError(null);
        }}
        className="self-start text-xs"
        style={{ color: "var(--color-text-muted)" }}
      >
        ← {email}
      </button>

      {/* coridian_, 2026-10-18: "it kind of hinders new users... because
          it's something that they have to look for in the fine print
          underneath login" — the sign-in/create-account choice was a tiny
          underlined text link below the submit button, easy to miss
          entirely. Now a real, equally-weighted segmented control right at
          the top of this step, same visual language the old page-level
          "Sign in / Create account" vs. "Try without an account" tabs
          used, so a new user sees both options before they even reach the
          password field instead of defaulting silently into sign-in. */}
      <div role="tablist" className="flex" style={{ borderBottom: "1px solid rgba(255, 255, 255, 0.12)" }}>
        <button
          type="button"
          role="tab"
          aria-selected={mode === "sign-in"}
          onClick={() => {
            setMode("sign-in");
            setAgeConfirmed(false);
            setError(null);
          }}
          className="flex-1 px-3 py-2 text-sm font-bold"
          style={{
            color: mode === "sign-in" ? "var(--color-accent)" : "var(--color-text-muted)",
            borderBottom: mode === "sign-in" ? "2px solid var(--color-accent)" : "none",
            marginBottom: "-1px",
          }}
        >
          Sign in
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={mode === "create-account"}
          onClick={() => {
            setMode("create-account");
            setError(null);
          }}
          className="flex-1 px-3 py-2 text-sm font-bold"
          style={{
            color: mode === "create-account" ? "var(--color-accent)" : "var(--color-text-muted)",
            borderBottom: mode === "create-account" ? "2px solid var(--color-accent)" : "none",
            marginBottom: "-1px",
          }}
        >
          Create account
        </button>
      </div>

      <form onSubmit={handleSubmit} className="flex flex-col gap-3">
        <label className="flex flex-col gap-1 text-sm" style={{ color: "var(--color-text-secondary)" }}>
          Password
          <input
            type="password"
            required
            autoFocus
            minLength={6}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            className="px-3 py-2.5"
            style={FIELD_STYLE}
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
            <button
              type="submit"
              disabled={busy}
              className="px-4 py-2.5 text-sm font-bold self-start"
              style={{
                background: "var(--color-accent-strong)",
                color: "var(--color-brand-mark-ink)",
                fontWeight: "var(--font-weight-button)",
                opacity: busy ? "var(--opacity-disabled)" : 1,
                borderRadius: "12px",
              }}
            >
              {mode === "sign-in" ? "Sign in" : "Create account"}
            </button>
          </>
        )}
      </form>
    </div>
  );
}
