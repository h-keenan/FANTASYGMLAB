import type { Session } from '@supabase/supabase-js';
import React, {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';

import { api } from '../lib/api';
import {
  didAuthenticatedUserChange,
  readStoredAuthScopeUserId,
  setCurrentAuthScopeUserId,
  writeStoredAuthScopeUserId,
} from '../lib/authScope';
import { canConvertGuestToAccount, validateGuestConversionInput } from '../lib/guestConversion';
import { clearAuthenticatedQueryCache } from '../lib/queryClient';
import { identifyRevenueCatUser, signOutRevenueCatUser } from '../lib/revenuecat';
import { syncLastLeagueFromServer } from '../lib/lastLeague';
import { syncPushToken, unregisterCurrentPushToken } from '../lib/pushNotifications';
import { supabase } from '../lib/supabase';
import { useDensity } from './DensityContext';
import { useThemeMode } from './ThemeModeContext';

interface AuthContextValue {
  session: Session | null;
  loading: boolean;
  signIn: (email: string, password: string) => Promise<{ error: string | null }>;
  signUp: (email: string, password: string) => Promise<{ error: string | null }>;
  signInAsGuest: () => Promise<{ error: string | null }>;
  signOut: () => Promise<void>;
  deleteAccount: () => Promise<{ error: string | null }>;
  /** True for a currently-signed-in guest (anonymous) session — see
   * lib/guestConversion.ts for why this is a materially different state
   * from a signed-out session. */
  isGuest: boolean;
  /**
   * Fix 3 (welcome/signup audit): upgrades the CURRENT guest session into a
   * real account in place via Supabase's own anonymous -> permanent
   * identity upgrade, rather than signing out and signing up as a
   * brand-new, unrelated user. Because `session.user.id` never changes,
   * every saved league/roster/preference already scoped to this guest's
   * id (saved_leagues, GM Targets, etc. — all RLS-scoped to
   * `auth.uid() = user_id`) stays reachable automatically; there is
   * nothing to snapshot or restore. No-op error when called outside a
   * guest session.
   */
  convertGuestToAccount: (email: string, password: string) => Promise<{ error: string | null }>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const { syncDensityFromServer } = useDensity();
  const { syncModeFromServer } = useThemeMode();
  // Requirement 5 (auth session change hardening): the last authenticated
  // user id this provider has actually acted on, primed from AsyncStorage
  // below so a cross-restart user swap (not just a same-session one) is
  // caught too. Compared via `didAuthenticatedUserChange`, which is a
  // no-op for an ordinary token refresh of the SAME user — only a genuine
  // user-id change triggers a cache clear.
  const lastHandledUserIdRef = useRef<string | null>(null);

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
        syncModeFromServer(result.theme_mode);
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

    // Requirement 5: if the authenticated user differs from whoever the
    // persisted query cache was last confirmed to belong to, clear it
    // *before* letting the rest of this effect proceed to sync/fetch that
    // user's private data. Also keeps queryKeys.ts's per-user key scoping
    // (authScope.ts) and the cross-restart marker in sync going forward.
    const handleAuthenticatedUserId = async (nextUserId: string | null) => {
      if (didAuthenticatedUserChange(lastHandledUserIdRef.current, nextUserId)) {
        await clearAuthenticatedQueryCache();
      }
      lastHandledUserIdRef.current = nextUserId;
      setCurrentAuthScopeUserId(nextUserId);
      await writeStoredAuthScopeUserId(AsyncStorage, nextUserId);
    };

    void (async () => {
      lastHandledUserIdRef.current = await readStoredAuthScopeUserId(AsyncStorage);
      if (!isMounted) return;

      const { data } = await supabase.auth.getSession();
      if (!isMounted) return;
      const nextUserId = data.session?.user?.id ?? null;
      await handleAuthenticatedUserId(nextUserId);
      if (!isMounted) return;

      setSession(data.session);
      setLoading(false);
      if (data.session) {
        void identifyRevenueCatUser(data.session.user.id);
        void syncPushToken();
        void syncDevicePreferences();
      }
    })();

    const { data: subscription } = supabase.auth.onAuthStateChange(
      (_event, nextSession) => {
        const nextUserId = nextSession?.user?.id ?? null;
        void (async () => {
          if (!isMounted) return;
          await handleAuthenticatedUserId(nextUserId);
          if (!isMounted) return;

          setSession(nextSession);
          if (nextSession) {
            void identifyRevenueCatUser(nextSession.user.id);
            void syncPushToken();
            void syncDevicePreferences();
          }
        })();
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
      isGuest: canConvertGuestToAccount(session),
      convertGuestToAccount: async (email, password) => {
        const validationError = validateGuestConversionInput(email, password);
        if (validationError) return { error: validationError };
        if (!canConvertGuestToAccount(session)) {
          return { error: 'Only a guest session can be converted to an account.' };
        }
        const { error } = await supabase.auth.updateUser({ email, password });
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
        // Push-token unregistering needs the still-active session/access
        // token to call the backend, so it must run before anything below
        // invalidates it.
        await unregisterCurrentPushToken();
        try {
          await supabase.auth.signOut();
          await signOutRevenueCatUser();
        } finally {
          // Requirement 1: always clear authenticated/persisted query
          // state on sign-out, even if supabase/RevenueCat sign-out above
          // threw — a cache-clear (or anything else here) failure must
          // never leave the user stuck unable to sign out, and stale
          // authenticated data must never survive to the next session
          // regardless of how sign-out got here. clearAuthenticatedQueryCache
          // itself never throws (see its own doc comment).
          await clearAuthenticatedQueryCache();
          lastHandledUserIdRef.current = null;
          setCurrentAuthScopeUserId(null);
          await writeStoredAuthScopeUserId(AsyncStorage, null);
        }
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
        // Same ordering/guarantee as signOut above: push-token unregister
        // first (needs the still-live session), then best-effort
        // sign-out/cache-teardown that always completes via `finally`.
        await unregisterCurrentPushToken();
        try {
          await supabase.auth.signOut();
          await signOutRevenueCatUser();
        } finally {
          await clearAuthenticatedQueryCache();
          lastHandledUserIdRef.current = null;
          setCurrentAuthScopeUserId(null);
          await writeStoredAuthScopeUserId(AsyncStorage, null);
        }
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
