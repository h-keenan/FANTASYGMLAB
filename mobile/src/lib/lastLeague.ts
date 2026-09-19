import AsyncStorage from '@react-native-async-storage/async-storage';

import { api } from './api';
import { isShowcaseModeEnabled } from './showcaseMode';

const KEY = 'fgl:last-league';

export interface LastLeague {
  leagueId: string;
  leagueName: string;
}

/**
 * Remembers the last league the user opened so the app can jump straight
 * back in on next launch instead of always landing on a bare leagues list.
 * Best-effort only — a storage failure just means "ask again," never a crash.
 */
export async function getLastLeague(): Promise<LastLeague | null> {
  try {
    const raw = await AsyncStorage.getItem(KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (parsed && typeof parsed.leagueId === 'string' && typeof parsed.leagueName === 'string') {
      return parsed;
    }
    return null;
  } catch {
    return null;
  }
}

export async function setLastLeague(league: LastLeague): Promise<void> {
  try {
    await AsyncStorage.setItem(KEY, JSON.stringify(league));
  } catch {
    // Best-effort — not worth surfacing to the user.
  }
  // In showcase mode the name in hand is a stand-in (lib/showcaseMode.ts),
  // so writing it durably would push a fake league name to this account's
  // other devices and the web app. Local cache only while recording.
  if (isShowcaseModeEnabled()) return;
  // Also durable (via the same user_settings blob display density uses) so
  // a reinstall or a second device picks up where this one left off, not
  // just this device's own AsyncStorage.
  api
    .updateDevicePreferences({ lastLeagueId: league.leagueId, lastLeagueName: league.leagueName })
    .catch(() => {});
}

/**
 * For AuthContext only: apply a last-league value fetched from the durable
 * /v1/preferences store into this device's local AsyncStorage cache,
 * without writing it back (avoids a redundant round trip).
 */
export async function syncLastLeagueFromServer(league: LastLeague): Promise<void> {
  try {
    await AsyncStorage.setItem(KEY, JSON.stringify(league));
  } catch {
    // Best-effort — not worth surfacing to the user.
  }
}
