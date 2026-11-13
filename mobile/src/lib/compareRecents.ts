import AsyncStorage from '@react-native-async-storage/async-storage';

import { pushRecent } from './compareHeadToHead';

const KEY = 'fgl:compare-recent';

/** Recently chosen compare opponents for a league (ids, newest first). Storage failures never throw. */
export async function readRecentOpponents(leagueId: string): Promise<string[]> {
  try {
    const raw = await AsyncStorage.getItem(`${KEY}:${leagueId}`);
    const parsed: unknown = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed.filter((id): id is string => typeof id === 'string') : [];
  } catch {
    return [];
  }
}

export async function rememberOpponent(leagueId: string, playerId: string): Promise<string[]> {
  const next = pushRecent(await readRecentOpponents(leagueId), playerId);
  try {
    await AsyncStorage.setItem(`${KEY}:${leagueId}`, JSON.stringify(next));
  } catch {
    // Recents just do not persist.
  }
  return next;
}
