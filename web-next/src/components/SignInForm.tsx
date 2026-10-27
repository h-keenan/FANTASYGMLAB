"use client";

import { useEffect, useState } from "react";

import { useAuth } from "@/context/AuthContext";
import { AgeGate } from "./AgeGate";
import { hasPassedAgeGate, setPassedAgeGate } from "@/lib/ageGateStorage";
import { Button } from "@/components/Button";
import { Input } from "@/components/Input";

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
  const { signIn, signUp, signInWithOAuth, upgradeGuestWithEmail, isGuest, callbackNotice, resetPassword } = useAuth();
  // Guest (anonymous) sessions are upgraded in place so the user id and saved
  // data are kept; the notice explains the rare cases where that is impossible.
  const [localNotice, setNotice] = useState<string | null>(null);
  const notice = localNotice ?? callbackNotice?.message ?? null;
  // Set once linking failed and the user must opt in to a plain sign-in.
  const [plainOAuthChosen, setPlainOAuth] = useState(false);
  const plainOAuth = plainOAuthChosen || Boolean(callbackNotice);
  const [step, setStep] = useState<"email" | "password" | "check-email">("email");
  const [ageConfirmed, setAgeConfirmed] = useState(false);
  // Provider waiting on the age gate (Google/Apple skip the password step, so
  // they get the same date-of-birth gate before redirecting; parity with the
  // mobile LoginScreen, which gates every auth path).
  const [oauthAgePending, setOauthAgePending] = useState<"google" | "apple" | null>(null);
  // "Forgot password?" (P0 UX audit, 2026-10-27): a real password-auth user
  // with no way to recover a forgotten password was a hard lockout on both
  // platforms. Mirrors mobile's LoginScreen resetMode toggle exactly, same
  // enumeration-safe notice copy, same supabase.auth.resetPasswordForEmail
  // call (via AuthContext.resetPassword) — only the completion step differs
  // (see PasswordRecoveryGate, mounted at the root layout).
  const [resetMode, setResetMode] = useState(false);
  const [resetBusy, setResetBusy] = useState(false);
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
  // signInWithOAuth redirects away from this page entirely, so the age gate
  // runs BEFORE it (UX audit 2026-10-27: OAuth used to skip it). A browser
  // that already cleared the gate once is not asked again.
  const handleOAuth = async (provider: "google" | "apple") => {
    if (!ageConfirmed && !hasPassedAgeGate()) {
      setError(null);
      setOauthAgePending(provider);
      return;
    }
    await handleOAuthConfirmed(provider);
  };

  const handleOAuthConfirmed = async (provider: "google" | "apple") => {
    setOauthBusy(provider);
    const result = plainOAuth ? await signInWithOAuth(provider, { plain: true }) : await signInWithOAuth(provider);
    if (result.fallback) {
      // Linking to the guest session is not possible; do NOT silently drop
      // the guest's data: ask first. Next click proceeds with plain sign-in.
      setOauthBusy(null);
      setPlainOAuth(true);
      setNotice(result.notice ?? null);
      return;
    }
    if (result.error) {
      setOauthBusy(null);
      setError(result.error);
    }
    // On success the browser navigates away to the provider; nothing left
    // to do here.
  };

  // Cancelling at Apple/Google (or pressing Back) returns here from the
  // browser's back/forward cache with oauthBusy still set, which left both
  // buttons disabled and grayed out. Clear it whenever the page comes back.
  useEffect(() => {
    const reset = () => setOauthBusy(null);
    const onPageShow = (event: PageTransitionEvent) => {
      if (event.persisted) reset();
    };
    const onVisible = () => {
      if (document.visibilityState === "visible") reset();
    };
    window.addEventListener("pageshow", onPageShow);
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      window.removeEventListener("pageshow", onPageShow);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, []);

  const handleEmailContinue = (event: React.FormEvent) => {
    event.preventDefault();
    if (!email) return;
    setStep("password");
  };

  const finishGuestUpgrade = async () => {
    const result = await upgradeGuestWithEmail(email, password);
    if (result.outcome === "converted") {
      setBusy(false);
      onSignedIn();
      return;
    }
    if (result.outcome === "confirm-email") {
      setBusy(false);
      setStep("check-email");
      return;
    }
    if (result.outcome === "email-exists") {
      // The email belongs to an existing account: keep the old behavior
      // (plain sign-in) after telling the user the guest data is not merged.
      setNotice(result.error);
      const signInResult = await signIn(email, password);
      setBusy(false);
      if (!signInResult.error) {
        onSignedIn();
        return;
      }
      setError("Incorrect password. Try again.");
      return;
    }
    setBusy(false);
    setError(result.error);
  };

  const finishSignUp = async () => {
    if (isGuest) {
      await finishGuestUpgrade();
      return;
    }
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

  const handleResetPassword = async (event: React.FormEvent) => {
    event.preventDefault();
    setResetBusy(true);
    setError(null);
    const result = await resetPassword(email);
    setResetBusy(false);
    if (result.error) {
      setError(result.error);
      return;
    }
    // Enumeration-safe: identical copy whether or not an account exists for
    // this email (mirrors mobile's LoginScreen and Supabase's own /recover
    // response).
    setNotice("If an account exists for that email, a password reset link has been sent. Check your inbox and spam folder.");
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    if (isGuest) {
      // Skip the sign-in-first attempt: signing in would replace the guest
      // session (new user id). Upgrade in place; fall back inside.
      if (!ageConfirmed) {
        setBusy(false);
        setNeedsAgeGate(true);
        return;
      }
      await finishGuestUpgrade();
      return;
    }
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
          {isGuest
            ? " Confirm it to finish creating your account. Everything you set up as a guest stays with it."
            : " Confirm your account, then come back here to sign in."}
        </p>
        <Button
          type="button"
          onClick={() => {
            setStep("password");
            setNeedsAgeGate(false);
            setError(null);
          }}
        style={{ alignSelf: "auto" }}
      >
          Back to sign in
        </Button>
      </div>
    );
  }

  if (step === "email" && oauthAgePending) {
    const provider = oauthAgePending;
    return (
      <div className="glass-surface flex flex-col gap-3 p-4">
        <AgeGate
          onConfirmed={() => {
            setAgeConfirmed(true);
            setPassedAgeGate();
            setOauthAgePending(null);
            void handleOAuthConfirmed(provider);
          }}
        />
        <button
          type="button"
          onClick={() => setOauthAgePending(null)}
          className="self-start text-xs inline-flex items-center min-h-[var(--touch-target-min)]"
          style={{ color: "var(--color-text-secondary)" }}
        >
          Back
        </button>
      </div>
    );
  }

  if (step === "email") {
    return (
      <div id="get-started" className="glass-surface flex flex-col gap-3 p-4">
        <form onSubmit={handleEmailContinue} className="flex flex-col gap-3">
          <div className="flex flex-col gap-0.5">
            <h2 className="text-lg font-extrabold" style={{ color: "var(--color-text-primary)" }}>
              Get started
            </h2>
            <p className="hidden sm:block text-sm" style={{ color: "var(--color-text-secondary)" }}>
              Enter your email to sign in or create an account.
            </p>
          </div>
          <label className="flex flex-col gap-1 text-sm" style={{ color: "var(--color-text-secondary)" }}>
            Email
            <Input
              type="email"
              required
              autoComplete="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
          </label>
          {notice ? (
            <p role="status" className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
              {notice}
            </p>
          ) : null}
          {error ? (
            <p role="alert" className="text-xs" style={{ color: "var(--color-danger)" }}>
              {error}
            </p>
          ) : null}
          <Button
            type="submit"
        style={{ alignSelf: "auto" }}
      >
            Continue
          </Button>
        </form>

        <div className="flex items-center gap-3">
          <div className="flex-1" style={{ height: "1px", background: "var(--color-border)" }} />
          <span className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
            or continue with
          </span>
          <div className="flex-1" style={{ height: "1px", background: "var(--color-border)" }} />
        </div>
        <div className="grid grid-cols-2 gap-2">
        <button
          type="button"
          aria-label={oauthBusy === "google" ? undefined : "Continue with Google"}
          onClick={() => handleOAuth("google")}
          disabled={oauthBusy !== null}
          className="glass-input px-4 py-2.5 text-sm font-bold min-h-[var(--touch-target-min)]"
          style={{
            color: "var(--color-text-primary)",
            borderRadius: "var(--radius-control)",
            opacity: oauthBusy !== null ? "var(--opacity-disabled)" : 1,
          }}
        >
          {oauthBusy === "google" ? "Redirecting to Google…" : "Google"}
        </button>
        <button
          type="button"
          aria-label={oauthBusy === "apple" ? undefined : "Continue with Apple"}
          onClick={() => handleOAuth("apple")}
          disabled={oauthBusy !== null}
          className="glass-input px-4 py-2.5 text-sm font-bold min-h-[var(--touch-target-min)]"
          style={{
            color: "var(--color-text-primary)",
            borderRadius: "var(--radius-control)",
            opacity: oauthBusy !== null ? "var(--opacity-disabled)" : 1,
          }}
        >
          {oauthBusy === "apple" ? "Redirecting to Apple…" : "Apple"}
        </button>
        </div>
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
        className="self-start text-xs inline-flex items-center min-h-[var(--touch-target-min)] max-w-full truncate"
        style={{ color: "var(--color-text-secondary)" }}
      >
        ← {email}
      </button>

      <h2 className="text-lg font-extrabold" style={{ color: "var(--color-text-primary)" }}>
        {resetMode ? "Reset your password" : "Create your account or sign in"}
      </h2>
      <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
        {resetMode
          ? "We'll email a link to set a new password."
          : "New here? Choose a password (6+ characters) to create your account. Already have one? Enter it to sign in."}
      </p>

      {resetMode ? (
        <form onSubmit={handleResetPassword} className="flex flex-col gap-3">
          {notice ? (
            <p role="status" className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
              {notice}
            </p>
          ) : null}
          {error ? (
            <p role="alert" className="text-xs" style={{ color: "var(--color-danger)" }}>
              {error}
            </p>
          ) : null}
          <Button type="submit" loading={resetBusy}>
            {resetBusy ? "Sending…" : "Send reset link"}
          </Button>
          <button
            type="button"
            onClick={() => {
              setResetMode(false);
              setError(null);
              setNotice(null);
            }}
            className="self-start text-xs"
            style={{ color: "var(--color-text-secondary)" }}
          >
            Back to sign in
          </button>
        </form>
      ) : needsAgeGate && !ageConfirmed ? (
        <AgeGate
          onConfirmed={() => {
            setAgeConfirmed(true);
            setPassedAgeGate();
            setNeedsAgeGate(false);
            setBusy(true);
            void finishSignUp();
          }}
        />
      ) : (
        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          <label className="flex flex-col gap-1 text-sm" style={{ color: "var(--color-text-secondary)" }}>
            Password
            <Input
              type="password"
              required
              autoFocus
              minLength={6}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </label>

          {notice ? (
            <p role="status" className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
              {notice}
            </p>
          ) : null}
          {error ? (
            <p role="alert" className="text-xs" style={{ color: "var(--color-danger)" }}>
              {error}
            </p>
          ) : null}
          <Button
            type="submit"
            loading={busy}
          >
            {busy ? "Continuing…" : "Continue"}
          </Button>
          {!isGuest ? (
            <button
              type="button"
              onClick={() => {
                setResetMode(true);
                setError(null);
                setNotice(null);
              }}
              className="self-start text-xs"
              style={{ color: "var(--color-text-secondary)" }}
            >
              Forgot password?
            </button>
          ) : null}
        </form>
      )}
    </div>
  );
}
