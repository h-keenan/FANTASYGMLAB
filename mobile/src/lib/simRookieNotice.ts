import AsyncStorage from '@react-native-async-storage/async-storage';

import { simRookieNoticeKey } from './simGame';

/**
 * Per-game "the generated rookie class popup was already dismissed" flag.
 * AsyncStorage on the app (web uses localStorage). Best-effort: a storage
 * failure only means the popup shows once more.
 */
export async function isSimRookieNoticeSeen(gameId: string): Promise<boolean> {
  try {
    return (await AsyncStorage.getItem(simRookieNoticeKey(gameId))) === '1';
  } catch {
    return false;
  }
}

export async function setSimRookieNoticeSeen(gameId: string): Promise<void> {
  try {
    await AsyncStorage.setItem(simRookieNoticeKey(gameId), '1');
  } catch {
    // Best-effort.
  }
}
