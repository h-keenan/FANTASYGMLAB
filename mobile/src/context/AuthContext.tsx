import type { Session } from '@supabase/supabase-js';
import React, {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';

import { api } from '../lib/api';
import { identifyRevenueCatUser, signOutRevenueCatUser } from '../lib/revenuecat';
import { syncLastLeagueFromServer } from '../lib/lastLeague';
import { syncPushToken, unregisterCurrentPushToken } from '../lib/pushNotifications';
import { supabase } from '../lib/supabase';
import { useDensity } from './DensityContext';

interface AuthContextValue {
  session: Session | null;
  loading: boolean;
  signIn: (email: string, password: string) => Promise<{ error: string | null }>;
  signUp: (email: string, password: string) => Promise<{ error: string | null }>;
  signInAsGuest: () => Promise<{ error: string | null }>;
  signOut: () => Promise<void>;
  deleteAccount: () => Promise<{ error: string | null }>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const { syncDensityFromServer } = useDensity();

  useEffect(() => {
    let isMounted = true;

    // Cross-device display density + last-viewed league (see
    // docs/roadmap notes on cross-platform persistence): fetched once per
    // sign-in, applied to this device's local caches. Best-effort — a
    // failure here just means this device keeps whatever it already had
    // locally, never a crash or a blocked sign-in.
    const syncDevicePreferences = async () => {
      try {
        const result = await api.getDevicePreferences();
        if (!result.ok) return;
        syncDensityFromServer(result.ui_density);
        if (result.last_league) {
          await syncLastLeagueFromServer({
            leagueId: result.last_league.league_id,
            leagueName: result.last_league.league_name,
          });
        }
      } catch {
        // Best-effort.
      }
    };

    supabase.auth.getSession().then(({ data }) => {
      if (!isMounted) return;
      setSession(data.session);
      setLoading(false);
      if (data.session) {
        void identifyRevenueCatUser(data.session.user.id);
        void syncPushToken();
        void syncDevicePreferences();
      }
    });

    const { data: subscription } = supabase.auth.onAuthStateChange(
      (_event, nextSession) => {
        setSession(nextSession);
        if (nextSession) {
          void identifyRevenueCatUser(nextSession.user.id);
          void syncPushToken();
          void syncDevicePreferences();
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
      deleteAccount: async () => {
        // public.delete_user() (docs/supabase_delete_account.sql) is
        // security definer but auth.uid()-scoped inside the function body —
        // this can only ever delete the caller's own row, regardless of
        // that elevated privilege. Deleting auth.users cascades to every
        // app table referencing it (profiles, gm_targets, saved_leagues,
        // trade_outcomes, etc.) — no separate per-table cleanup needed.
        const { error } = await supabase.rpc('delete_user');
        if (error) return { error: error.message };
        await unregisterCurrentPushToken();
        await supabase.auth.signOut();
        await signOutRevenueCatUser();
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
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
