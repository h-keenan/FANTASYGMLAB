"use client";

import type { Session } from "@supabase/supabase-js";
import React, { createContext, useContext, useEffect, useMemo, useState } from "react";

import { supabase } from "@/lib/supabase";

interface AuthContextValue {
  session: Session | null;
  loading: boolean;
  signIn: (email: string, password: string) => Promise<{ error: string | null }>;
  /** `signedIn` is true only when Supabase returned an active session
   * immediately (project has email auto-confirm on) — callers must not
   * treat a successful signUp as "signed in" when it's false, since no
   * session exists yet (confirmation email pending). */
  signUp: (email: string, password: string) => Promise<{ error: string | null; signedIn: boolean }>;
  signInWithOAuth: (provider: "google" | "apple") => Promise<{ error: string | null }>;
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
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;

    void (async () => {
      const { data } = await supabase.auth.getSession();
      if (!isMounted) return;
      setSession(data.session);
      setLoading(false);
    })();

    const { data: subscription } = supabase.auth.onAuthStateChange((_event, nextSession) => {
      if (!isMounted) return;
      setSession(nextSession);
      setLoading(false);
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
      signIn: async (email, password) => {
        const { error } = await supabase.auth.signInWithPassword({ email, password });
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
          return { error: "An account with this email already exists. Try signing in instead.", signedIn: false };
        }
        return { error: null, signedIn: Boolean(data.session) };
      },
      signInWithOAuth: async (provider) => {
        const { error } = await supabase.auth.signInWithOAuth({
          provider,
          options: { redirectTo: typeof window !== "undefined" ? window.location.origin : undefined },
        });
        return { error: error?.message ?? null };
      },
      signInAsGuest: async () => {
        // Requires "Allow anonymous sign-ins" enabled in the Supabase
        // project (already on, since mobile uses this same call) — see
        // mobile/src/context/AuthContext.tsx's signInAsGuest comment.
        const { error } = await supabase.auth.signInAnonymously();
        return { error: error?.message ?? null };
      },
      signOut: async () => {
        await supabase.auth.signOut();
      },
      deleteAccount: async () => {
        const { error } = await supabase.rpc("delete_user");
        if (error) return { error: error.message };
        await supabase.auth.signOut();
        return { error: null };
      },
    }),
    [session, loading],
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
