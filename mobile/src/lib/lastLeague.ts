import AsyncStorage from '@react-native-async-storage/async-storage';

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
}
