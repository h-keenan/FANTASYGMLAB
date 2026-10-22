import AsyncStorage from '@react-native-async-storage/async-storage';

import { createAlertReadSync } from './alertReadSync';
import { api } from './api';
import { supabase } from './supabase';

/** App wiring for lib/alertReadSync.ts: AsyncStorage + the real POST. */
export const alertReadSync = createAlertReadSync(AsyncStorage, (leagueId, alertKey) =>
  api.markAlertRead(leagueId, alertKey),
);

/** Signed-in account id that scopes not-yet-synced reads ('' if none). */
export async function currentAlertReadUserId(): Promise<string> {
  try {
    const { data } = await supabase.auth.getSession();
    return data.session?.user?.id ?? '';
  } catch {
    return '';
  }
}
