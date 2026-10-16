import AsyncStorage from '@react-native-async-storage/async-storage';

const KEY = 'fgl:trial-lapsed-shown-expiration';

/**
 * Which lapsed-trial expiration date this device already showed the
 * "your trial ended" interstitial for — keyed to the expiration itself
 * (not just a boolean) so a user who starts and lapses a second trial later
 * sees it again, rather than being permanently suppressed by the first one.
 */
export async function getShownTrialLapseExpiration(): Promise<string | null> {
  try {
    return await AsyncStorage.getItem(KEY);
  } catch {
    return null;
  }
}

export async function setShownTrialLapseExpiration(expiration: string): Promise<void> {
  try {
    await AsyncStorage.setItem(KEY, expiration);
  } catch {
    // Best-effort — worst case it shows again next launch.
  }
}
