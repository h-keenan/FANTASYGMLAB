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
  /** Redirect-based — the browser navigates away to the provider and back,
   * so there is no session to return here; AuthContext's own
   * onAuthStateChange listener picks up the resulting session on return,
   * same as every other auth method. Requires the provider configured with
   * real credentials in the Supabase dashboard (Google/Apple OAuth client
   * id+secret) — calling it before that is configured surfaces Supabase's
   * own "Unsupported provider" error. */
  signInWithOAuth: (provider: "google" | "apple") => Promise<{ error: string | null }>;
  signInAsGuest: () => Promise<{ error: string | null }>;
  signOut: () => Promise<void>;
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
        return { error: error?.message ?? null, signedIn: Boolean(data.session) };
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
