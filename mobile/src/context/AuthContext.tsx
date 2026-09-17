import type { Session } from '@supabase/supabase-js';
import React, {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';

import { identifyRevenueCatUser, signOutRevenueCatUser } from '../lib/revenuecat';
import { syncPushToken, unregisterCurrentPushToken } from '../lib/pushNotifications';
import { supabase } from '../lib/supabase';

interface AuthContextValue {
  session: Session | null;
  loading: boolean;
  signIn: (email: string, password: string) => Promise<{ error: string | null }>;
  signUp: (email: string, password: string) => Promise<{ error: string | null }>;
  signInAsGuest: () => Promise<{ error: string | null }>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;

    supabase.auth.getSession().then(({ data }) => {
      if (!isMounted) return;
      setSession(data.session);
      setLoading(false);
      if (data.session) {
        void identifyRevenueCatUser(data.session.user.id);
        void syncPushToken();
      }
    });

    const { data: subscription } = supabase.auth.onAuthStateChange(
      (_event, nextSession) => {
        setSession(nextSession);
        if (nextSession) {
          void identifyRevenueCatUser(nextSession.user.id);
          void syncPushToken();
        }
      },
    );

    return () => {
      isMounted = false;
      subscription.subscription.unsubscribe();
    };
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      session,
      loading,
      signIn: async (email, password) => {
        const { error } = await supabase.auth.signInWithPassword({ email, password });
        return { error: error?.message ?? null };
      },
      signUp: async (email, password) => {
        // Without this, Supabase's confirmation link falls back to the
        // project's Site URL — the web app — which is a confusing surface
        // switch for someone who started signing up on mobile. This at
        // least opens back into this app; Apple/Google sign-in (no email
        // confirmation step at all) is the real fix for that flow.
        const { error } = await supabase.auth.signUp({
          email,
          password,
          options: { emailRedirectTo: 'fantasygmlab://' },
        });
        return { error: error?.message ?? null };
      },
      signInAsGuest: async () => {
        // Requires "Allow anonymous sign-ins" enabled in the Supabase
        // dashboard (Authentication -> Settings) — a project config toggle,
        // not something this call can turn on itself. Everything
        // downstream (saved leagues, Sleeper linking, entitlement) keys off
        // the session's user id, never email, so an anonymous session works
        // transparently through the rest of the app.
        const { error } = await supabase.auth.signInAnonymously();
        return { error: error?.message ?? null };
      },
      signOut: async () => {
        await unregisterCurrentPushToken();
        await supabase.auth.signOut();
        await signOutRevenueCatUser();
      },
    }),
    [session, loading],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
