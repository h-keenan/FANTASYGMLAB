"use client";

import type { Session } from "@supabase/supabase-js";
import React, { createContext, useContext, useEffect, useMemo, useRef, useState } from "react";

import { trackFeatureUse } from "@/lib/analytics";
import { billingRequest } from "@/lib/billingClient";
import {
  GUEST_DATA_NOT_MERGED_NOTICE,
  IDENTITY_EXISTS_NOTICE,
  LINK_UNAVAILABLE_NOTICE,
  classifyEmailUpgradeResult,
  classifyUpgradeError,
  clearReturnPath,
  parseAuthCallbackError,
  readReturnPath,
  shouldRestoreReturnPath,
  storeReturnPath,
  type GuestUpgradeFailure,
} from "@/lib/guestUpgrade";
import { clearPortfolioSnapshots } from "@/lib/portfolioSnapshot";
import { storeCurrentPathForReturnAfterSignIn } from "@/lib/protectedRouteReturn";
import { clearSessionEnded, isForcedSignOut, markSessionEnded, readSessionEnded } from "@/lib/sessionEnded";
import { supabase } from "@/lib/supabase";
import { applySessionUser } from "@/lib/userStorage";

/** Current in-app location (path + query + hash) to come back to after auth. */
function currentLocationPath(): string {
  if (typeof window === "undefined") return "/";
  return window.location.pathname + window.location.search + window.location.hash;
}

function safeLocalStorage(): Storage | null {
  try {
    return typeof window === "undefined" ? null : window.localStorage;
  } catch {
    return null;
  }
}

function safeSessionStorage(): Storage | null {
  try {
    return typeof window === "undefined" ? null : window.sessionStorage;
  } catch {
    return null;
  }
}

export type GuestEmailUpgradeOutcome = "converted" | "confirm-email" | "email-exists" | "error";

interface AuthContextValue {
  session: Session | null;
  loading: boolean;
  signIn: (email: string, password: string) => Promise<{ error: string | null }>;
  /** `signedIn` is true only when Supabase returned an active session
   * immediately (project has email auto-confirm on) — callers must not
   * treat a successful signUp as "signed in" when it's false, since no
   * session exists yet (confirmation email pending). */
  signUp: (email: string, password: string) => Promise<{ error: string | null; signedIn: boolean }>;
  /** For a guest session this LINKS the provider identity to the existing
   * anonymous user (id preserved). `fallback` is set when linking could not be
   * done and the caller must warn that guest data will not carry over; call
   * again with `{ plain: true }` to proceed with a normal sign-in anyway. */
  signInWithOAuth: (
    provider: "google" | "apple",
    options?: { plain?: boolean },
  ) => Promise<{ error: string | null; fallback?: "link-unavailable" | "identity-exists"; notice?: string }>;
  /** Guest-only: upgrade the anonymous user in place with email + password
   * (auth.updateUser), preserving the user id. "email-exists" means the email
   * belongs to another account (guest data cannot be merged). */
  upgradeGuestWithEmail: (
    email: string,
    password: string,
  ) => Promise<{ error: string | null; outcome: GuestEmailUpgradeOutcome }>;
  /** Set when returning from a failed provider link (e.g. identity already
   * exists / manual linking disabled). */
  callbackNotice: { fallback: "link-unavailable" | "identity-exists"; message: string } | null;
  signInAsGuest: () => Promise<{ error: string | null }>;
  signOut: () => Promise<void>;
  /** Account page (2026-10-19) — self-service account deletion, Apple App
   * Store Guideline 5.1.1(v) parity with mobile's existing "Delete
   * account" flow (mobile/src/context/AuthContext.tsx). Calls the same
   * `public.delete_user()` Supabase RPC (docs/supabase_delete_account.sql)
   * directly with the caller's own session — security-definer but
   * auth.uid()-scoped inside the function body, so this can only ever
   * delete the caller's own row. Deleting auth.users cascades to every
   * app table referencing it (profiles, saved_leagues, gm_targets, etc.),
   * so no separate per-table cleanup is needed here. */
  deleteAccount: () => Promise<{ error: string | null }>;
  /** True for a currently-signed-in guest (anonymous) session — mirrors
   * mobile's `isGuest` (mobile/src/lib/guestConversion.ts). A guest here is
   * a real Supabase session (`signInAnonymously`), not Streamlit's
   * sessionless model — see PR description for why Revision 1 follows
   * mobile's reference implementation instead. */
  isGuest: boolean;
  /** Forgot-password (P0 UX audit, 2026-10-27): sends the Supabase recovery
   * email. Same call as mobile (mobile/src/context/AuthContext.tsx,
   * supabase.auth.resetPasswordForEmail) with no redirectTo override — the
   * link lands on this web app via the project's default Site URL, which is
   * also where recoveryPending below picks it up. Always report success
   * (enumeration-safe) regardless of whether the email has an account,
   * mirroring mobile's identical notice copy; only a real send failure
   * (rate limit, bad request) surfaces an error. */
  resetPassword: (email: string) => Promise<{ error: string | null }>;
  /** True once Supabase's recovery link has established a session and
   * fired the PASSWORD_RECOVERY auth event. The caller must render a
   * blocking "set a new password" UI while this is true — the session is
   * real but the user hasn't actually proven a new password yet, so normal
   * app content should not be reachable (see PasswordRecoveryGate). */
  recoveryPending: boolean;
  /** True after a sign-out the user did not ask for (revoked elsewhere, account removed, other tab): the sign-in form says why. */
  sessionEnded?: boolean;
  /** Finishes a recovery: sets the new password on the recovery session.
   * Clears recoveryPending on success so the gate unmounts. */
  completeRecovery: (password: string) => Promise<{ error: string | null }>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const [callbackNotice, setCallbackNotice] = useState<AuthContextValue["callbackNotice"]>(null);
  const [recoveryPending, setRecoveryPending] = useState(false);
  const [sessionEnded, setSessionEnded] = useState(false);
  const sessionRef = useRef<Session | null>(null);
  // Set while the user's own sign-out / account deletion is running, so it is not reported as "your session ended".
  const userSignOutRef = useRef(false);

  // A failed provider link comes back as error params on the callback URL.
  useEffect(() => {
    if (typeof window === "undefined") return;
    const err = parseAuthCallbackError(window.location.search, window.location.hash);
    if (!err) return;
    const kind: GuestUpgradeFailure = classifyUpgradeError({ code: err.code, message: err.description });
    /* Reads the external callback URL once on mount; not derivable during render (SSR). */
    /* eslint-disable react-hooks/set-state-in-effect */
    if (kind === "identity-exists") {
      setCallbackNotice({ fallback: "identity-exists", message: IDENTITY_EXISTS_NOTICE });
      clearReturnPath(safeLocalStorage());
    } else if (kind === "link-unavailable") {
      setCallbackNotice({ fallback: "link-unavailable", message: LINK_UNAVAILABLE_NOTICE });
      clearReturnPath(safeLocalStorage());
    }
    /* eslint-enable react-hooks/set-state-in-effect */
  }, []);

  // After a guest upgrade (OAuth link or email confirmation, possibly in a
  // new tab) put the user back where they started instead of "/".
  useEffect(() => {
    if (loading || typeof window === "undefined") return;
    const storage = safeLocalStorage();
    const stored = readReturnPath(storage);
    if (
      shouldRestoreReturnPath({
        stored,
        hasSession: Boolean(session),
        isAnonymous: Boolean(session?.user?.is_anonymous),
        currentPath: window.location.pathname + window.location.search,
      })
    ) {
      clearReturnPath(storage);
      window.location.replace(stored as string);
    } else if (stored && session && !session.user?.is_anonymous) {
      clearReturnPath(storage);
    }
  }, [loading, session]);

  useEffect(() => {
    let isMounted = true;

    void (async () => {
      const { data } = await supabase.auth.getSession();
      if (!isMounted) return;
      // Storage learns the user before any child reads per-user state.
      applySessionUser(data.session?.user?.id ?? null);
      sessionRef.current = data.session;
      // A forced sign-out followed by a reload: the note must still be there when the sign-in form shows.
      if (!data.session && readSessionEnded(safeSessionStorage())) setSessionEnded(true);
      setSession(data.session);
      setLoading(false);
    })();

    const { data: subscription } = supabase.auth.onAuthStateChange((event, nextSession) => {
      if (!isMounted) return;
      // Purge a departing user's local state first, so the return path stored below (for the same user) survives it.
      applySessionUser(nextSession?.user?.id ?? null);
      if (isForcedSignOut({ event, hadSession: Boolean(sessionRef.current), userInitiated: userSignOutRef.current })) {
        // Pages are about to bounce a null session to "/": remember why, and where the user was, before they do.
        markSessionEnded(safeSessionStorage());
        storeCurrentPathForReturnAfterSignIn();
        setSessionEnded(true);
      } else if (nextSession) {
        clearSessionEnded(safeSessionStorage());
        setSessionEnded(false);
      }
      if (event === "SIGNED_OUT") userSignOutRef.current = false;
      sessionRef.current = nextSession;
      setSession(nextSession);
      setLoading(false);
      // Fired once the recovery link in the email is opened and Supabase
      // (via detectSessionInUrl) establishes a session from it. The user
      // must still prove a new password before using this session for
      // anything else — see PasswordRecoveryGate, mounted at the root
      // layout so it catches the link regardless of which page it lands on.
      if (event === "PASSWORD_RECOVERY") setRecoveryPending(true);
    });

    return () => {
      isMounted = false;
      subscription.subscription.unsubscribe();
    };
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      session,
      loading,
      isGuest: Boolean(session?.user?.is_anonymous),
      callbackNotice,
      signIn: async (email, password) => {
        const { error } = await supabase.auth.signInWithPassword({ email, password });
        // Real login/signup instrumentation: these events existed in the
        // canonical taxonomy (modules.launch_analytics.TRACKED_EVENTS) but
        // no web-next call site ever fired them (Founder Analytics audit,
        // 2026-10). dedupe: false -- every real sign-in is its own
        // countable event, not a reached-once milestone.
        if (!error) trackFeatureUse("login_completed", { dedupe: false });
        return { error: error?.message ?? null };
      },
      signUp: async (email, password) => {
        const { data, error } = await supabase.auth.signUp({
          email,
          password,
          options: { emailRedirectTo: typeof window !== "undefined" ? window.location.origin : undefined },
        });
        if (error) return { error: error.message, signedIn: false };
        // coridian_, 2026-10-18: "I create an account. It doesn't say
        // anything... I try to sign in again and nothing happens, and it
        // just says invalid." Root cause: Supabase's anti-enumeration
        // behavior — calling signUp for an email that ALREADY has an
        // account returns no error and no session, identical on the wire
        // to "brand new signup, confirmation email pending." The only
        // client-visible signal that tells these apart is `identities`:
        // empty for an existing account (confirmed, so no email was ever
        // sent for *this* call), non-empty for a genuinely new one. Every
        // caller of this before today silently treated both as "check
        // your email," which is actively wrong and misleading for an
        // account that already exists — the real fix here, not just a
        // UI polish pass.
        if (data.user && data.user.identities && data.user.identities.length === 0) {
          // Anti-enumeration path: this is an EXISTING account, not a new
          // signup -- no signup event for it.
          return { error: "An account with this email already exists. Try signing in instead.", signedIn: false };
        }
        // signed in immediately (email auto-confirm on) vs. confirmation
        // email pending -- both are a genuinely new account, so both are
        // tracked, just as two different funnel steps.
        trackFeatureUse(data.session ? "signup_completed" : "signup_started", { dedupe: false });
        return { error: null, signedIn: Boolean(data.session) };
      },
      signInWithOAuth: async (provider, options) => {
        const redirectTo = typeof window !== "undefined" ? window.location.origin : undefined;
        if (session?.user?.is_anonymous && !options?.plain) {
          // Guest: link the identity to the SAME user (needs "Allow manual
          // linking" in the Supabase Dashboard). redirectTo stays the bare
          // origin (already allow-listed); the return path is stashed locally.
          storeReturnPath(safeLocalStorage(), currentLocationPath());
          const { error } = await supabase.auth.linkIdentity({ provider, options: { redirectTo } });
          if (!error) return { error: null };
          clearReturnPath(safeLocalStorage());
          const kind = classifyUpgradeError(error);
          if (kind === "link-unavailable") {
            return { error: null, fallback: "link-unavailable", notice: LINK_UNAVAILABLE_NOTICE };
          }
          if (kind === "identity-exists") {
            return { error: null, fallback: "identity-exists", notice: IDENTITY_EXISTS_NOTICE };
          }
          return { error: error.message };
        }
        const { error } = await supabase.auth.signInWithOAuth({ provider, options: { redirectTo } });
        return { error: error?.message ?? null };
      },
      upgradeGuestWithEmail: async (email, password) => {
        const emailRedirectTo = typeof window !== "undefined" ? window.location.origin : undefined;
        storeReturnPath(safeLocalStorage(), currentLocationPath());
        const { data, error } = await supabase.auth.updateUser({ email, password }, { emailRedirectTo });
        if (error) {
          clearReturnPath(safeLocalStorage());
          if (classifyUpgradeError(error) === "email-exists") {
            return { error: GUEST_DATA_NOT_MERGED_NOTICE, outcome: "email-exists" };
          }
          return { error: error.message, outcome: "error" };
        }
        const outcome = classifyEmailUpgradeResult(data.user, email);
        if (outcome === "converted") clearReturnPath(safeLocalStorage());
        return { error: null, outcome };
      },
      signInAsGuest: async () => {
        // Requires "Allow anonymous sign-ins" enabled in the Supabase
        // project (already on, since mobile uses this same call) — see
        // mobile/src/context/AuthContext.tsx's signInAsGuest comment.
        const { error } = await supabase.auth.signInAnonymously();
        return { error: error?.message ?? null };
      },
      signOut: async () => {
        userSignOutRef.current = true;
        setRecoveryPending(false);
        // The cached Portfolio is one person's leagues: gone with the session.
        clearPortfolioSnapshots(safeLocalStorage());
        applySessionUser(null);
        await supabase.auth.signOut();
      },
      deleteAccount: async () => {
        // The delete-account edge function cancels any Stripe subscription
        // FIRST, then deletes the user (supabase/functions/delete-account).
        // If billing cannot be cancelled it refuses, so nobody is left
        // deleted-but-still-billed.
        const { data } = await supabase.auth.getSession();
        const accessToken = data.session?.access_token;
        if (!accessToken) return { error: "Sign in again to delete your account." };
        try {
          await billingRequest("delete-account", accessToken, { method: "POST", jsonBody: {}, backend: "supabase" });
        } catch (e) {
          return { error: e instanceof Error ? e.message : "Could not delete the account." };
        }
        userSignOutRef.current = true;
        applySessionUser(null);
        await supabase.auth.signOut();
        return { error: null };
      },
      resetPassword: async (email) => {
        const { error } = await supabase.auth.resetPasswordForEmail(email);
        return { error: error?.message ?? null };
      },
      recoveryPending,
      sessionEnded,
      completeRecovery: async (password) => {
        const { error } = await supabase.auth.updateUser({ password });
        if (error) return { error: error.message };
        setRecoveryPending(false);
        return { error: null };
      },
    }),
    [session, loading, callbackNotice, recoveryPending, sessionEnded],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
