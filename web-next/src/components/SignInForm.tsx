"use client";

import { useState } from "react";

import { useAuth } from "@/context/AuthContext";
import { AgeGate } from "./AgeGate";

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
 *
 * Rebuilt again, same day (Zach, all caps, after the segmented-control
 * version above shipped): "EMAIL AUTH STILL FUCKING BROKEN, I PUT THE
 * EMAIL IN, THEN IT ASKS ME TO SIGN IN OR CREATE ACCOUNT WHEN THAT SHOULD
 * BE AUTOMATICALLY DONE." The explicit Sign in/Create account tabs above
 * were themselves a deliberate fix for a real, separate complaint earlier
 * today (coridian_: the old buried text link was too easy to miss) — this
 * isn't reverting that fix, it's removing the need for ANY pre-choice at
 * all. Step 2 is now just password + one Continue button: attempt
 * signIn first, and only on failure attempt signUp — reusing the exact
 * identities-array signal the "already exists" root-cause fix above
 * already computes to tell "wrong password on a real account" apart from
 * "no account yet" (Supabase's sign-in error is identical generic text
 * for both, same anti-enumeration behavior as signUp). Neither stakeholder
 * ask is actually in conflict: there's no hidden link to miss (coridian_'s
 * original complaint) because there's nothing to choose at all, and it
 * resolves automatically either way (Zach's ask).
 */
export function SignInForm({ onSignedIn }: { onSignedIn: () => void }) {
  const { signIn, signUp, signInWithOAuth } = useAuth();
  const [step, setStep] = useState<"email" | "password" | "check-email">("email");
  const [ageConfirmed, setAgeConfirmed] = useState(false);
  // Set only once signIn has actually failed and this turned out to need
  // the signUp fallback — an existing user who signs in correctly never
  // sees this at all.
  const [needsAgeGate, setNeedsAgeGate] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [oauthBusy, setOauthBusy] = useState<"google" | "apple" | null>(null);

  // Google/Apple both enabled and verified working in Supabase, 2026-10-18.
  // signInWithOAuth redirects away from this page entirely (Supabase
  // handles the callback) — there's no intermediate step here to gate an
  // age check behind the way the email flow does, same gap the original
  // build of these buttons already accepted.
  const handleOAuth = async (provider: "google" | "apple") => {
    setOauthBusy(provider);
    const result = await signInWithOAuth(provider);
    if (result.error) {
      setOauthBusy(null);
      setError(result.error);
    }
    // On success the browser navigates away to the provider; nothing left
    // to do here.
  };

  const handleEmailContinue = (event: React.FormEvent) => {
    event.preventDefault();
    if (!email) return;
    setStep("password");
  };

  const finishSignUp = async () => {
    const result = await signUp(email, password);
    setBusy(false);
    if (result.error) {
      // "already exists" only comes back from signUp's own identities
      // check — meaning signIn's earlier generic failure was actually a
      // wrong password on a real account, not a missing one.
      setError(
        result.error.toLowerCase().includes("already exists")
          ? "Incorrect password. Try again."
          : result.error,
      );
      return;
    }
    if (result.signedIn) {
      onSignedIn();
      return;
    }
    // coridian_, 2026-10-18: "I create an account. It doesn't say
    // anything. It takes me back to the default sign-in page..." — a
    // small text notice folded back into the sign-in form (now gone)
    // was too easy to miss, especially for the one outcome a new user
    // most needs to actually notice. A full dedicated screen can't be
    // scrolled past unread.
    setStep("check-email");
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    const signInResult = await signIn(email, password);
    if (!signInResult.error) {
      setBusy(false);
      onSignedIn();
      return;
    }
    // Could be "no account yet" (a genuinely new user) or "wrong password"
    // on an existing one — confirm age before the signUp attempt that
    // would disambiguate them, never retroactively once an account might
    // already exist, same as the age gate every other account-creating
    // path in this app (the guest tab's own AgeGate) already requires.
    if (!ageConfirmed) {
      setBusy(false);
      setNeedsAgeGate(true);
      return;
    }
    await finishSignUp();
  };

  if (step === "check-email") {
    return (
      <div className="glass-surface flex flex-col gap-4 p-6 text-center items-center">
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
            setNeedsAgeGate(false);
            setError(null);
          }}
          className="px-4 py-2.5 text-sm font-bold"
          style={{
            background: "var(--color-accent-strong)",
            color: "var(--color-on-accent)",
            fontWeight: "var(--font-weight-button)",
            borderRadius: "var(--radius-control)",
          }}
        >
          Back to sign in
        </button>
      </div>
    );
  }

  if (step === "email") {
    return (
      <div className="glass-surface flex flex-col gap-4 p-6">
        <form onSubmit={handleEmailContinue} className="flex flex-col gap-4">
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
              className="glass-input px-3 py-2.5"
              style={{ color: "var(--color-text-primary)" }}
            />
          </label>
          {error ? (
            <p role="alert" className="text-xs" style={{ color: "var(--color-danger)" }}>
              {error}
            </p>
          ) : null}
          <button
            type="submit"
            className="px-4 py-2.5 text-sm font-bold"
            style={{
              background: "var(--color-accent-strong)",
              color: "var(--color-on-accent)",
              fontWeight: "var(--font-weight-button)",
              borderRadius: "var(--radius-control)",
            }}
          >
            Continue
          </button>
        </form>

        <div className="flex items-center gap-3">
          <div className="flex-1" style={{ height: "1px", background: "var(--color-border)" }} />
          <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
            or
          </span>
          <div className="flex-1" style={{ height: "1px", background: "var(--color-border)" }} />
        </div>
        <button
          type="button"
          onClick={() => handleOAuth("google")}
          disabled={oauthBusy !== null}
          className="glass-input px-4 py-2.5 text-sm font-bold"
          style={{
            color: "var(--color-text-primary)",
            borderRadius: "var(--radius-control)",
            opacity: oauthBusy !== null ? "var(--opacity-disabled)" : 1,
          }}
        >
          {oauthBusy === "google" ? "Redirecting to Google…" : "Continue with Google"}
        </button>
        <button
          type="button"
          onClick={() => handleOAuth("apple")}
          disabled={oauthBusy !== null}
          className="glass-input px-4 py-2.5 text-sm font-bold"
          style={{
            color: "var(--color-text-primary)",
            borderRadius: "var(--radius-control)",
            opacity: oauthBusy !== null ? "var(--opacity-disabled)" : 1,
          }}
        >
          {oauthBusy === "apple" ? "Redirecting to Apple…" : "Continue with Apple"}
        </button>
      </div>
    );
  }

  return (
    <div className="glass-surface flex flex-col gap-4 p-6">
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

      <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
        Enter your password to continue — we&apos;ll sign you in, or set up your account if this is your first time.
      </p>

      {needsAgeGate && !ageConfirmed ? (
        <AgeGate
          onConfirmed={() => {
            setAgeConfirmed(true);
            setNeedsAgeGate(false);
            setBusy(true);
            void finishSignUp();
          }}
        />
      ) : (
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
              className="glass-input px-3 py-2.5"
              style={{ color: "var(--color-text-primary)" }}
            />
          </label>

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
              color: "var(--color-on-accent)",
              fontWeight: "var(--font-weight-button)",
              opacity: busy ? "var(--opacity-disabled)" : 1,
              borderRadius: "var(--radius-control)",
            }}
          >
            {busy ? "Continuing…" : "Continue"}
          </button>
        </form>
      )}
    </div>
  );
}
