import AsyncStorage from '@react-native-async-storage/async-storage';

const KEY = 'fgl:age-gate-passed';
export const MINIMUM_AGE = 13;

/**
 * COPPA age-gate: FantasyGM Lab isn't directed at children, but with no age
 * check at all a signup flow (email, Apple, Google) can't distinguish an
 * adult from a child. This is a device-local, one-time gate shown before
 * LoginScreen's actual auth UI — a neutral date-of-birth entry, not a "I am
 * 13+" checkbox (which the FTC treats as coaching the answer, not a real
 * age check). Nothing about the entered date is persisted anywhere, on
 * device or server — only a plain boolean "this device already cleared the
 * gate" flag, so a returning adult isn't asked again every launch.
 */
export async function hasPassedAgeGate(): Promise<boolean> {
  try {
    return (await AsyncStorage.getItem(KEY)) === 'true';
  } catch {
    return false;
  }
}

export async function setPassedAgeGate(): Promise<void> {
  try {
    await AsyncStorage.setItem(KEY, 'true');
  } catch {
    // Best-effort — worst case the gate shows again next launch.
  }
}

export function calculateAge(birthDate: Date, today: Date = new Date()): number {
  let age = today.getFullYear() - birthDate.getFullYear();
  const monthDiff = today.getMonth() - birthDate.getMonth();
  if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < birthDate.getDate())) {
    age -= 1;
  }
  return age;
}
