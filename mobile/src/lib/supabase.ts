import 'react-native-url-polyfill/auto';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { AppState } from 'react-native';
import { createClient } from '@supabase/supabase-js';

import { SLOW_REQUEST_MESSAGE } from './badDayCopy';
import { env } from './env';
import { withReadTimeout } from './requestTimeouts';

// Same Supabase project as the web app (auth.users, profiles.entitlement) —
// accounts and premium status carry over between web and mobile.
export const supabase = createClient(env.supabaseUrl, env.supabaseAnonKey, {
  auth: {
    storage: AsyncStorage,
    autoRefreshToken: true,
    persistSession: true,
    detectSessionInUrl: false,
  },
  // The one place PostgREST reads get a client timeout (lib/requestTimeouts.ts); auth calls and writes pass through.
  global: { fetch: withReadTimeout((input, init) => fetch(input, init), { message: SLOW_REQUEST_MESSAGE }) },
});

// autoRefreshToken's setTimeout is suspended by the OS while the app is
// backgrounded — soft-closing the app for longer than the access token's
// lifetime and reopening it left every request racing a stale/expired token,
// surfacing as a bare "network error" instead of a clean re-auth. Supabase's
// own React Native guidance is to drive the refresh loop off AppState
// directly rather than relying on background timers.
AppState.addEventListener('change', (state) => {
  if (state === 'active') {
    void supabase.auth.startAutoRefresh();
  } else {
    void supabase.auth.stopAutoRefresh();
  }
});
