import AsyncStorage from '@react-native-async-storage/async-storage';
import { Linking } from 'react-native';

import { parseReferralCode } from './referralCode';

/**
 * Mobile twin of web-next/src/lib/attribution.ts' referral capture. An invite
 * link (`.../?ref=CODE`, or the app scheme `fantasygmlab://...?ref=CODE`) that
 * opens the app is remembered here and sent as `referral_code` with the first
 * Sleeper username lookup, which is the server-side moment a referral is
 * credited. App analytics stay off: this only stores the code on-device.
 */
const KEY = 'fgl:pending-referral-code';

export async function getPendingReferralCode(): Promise<string> {
  try {
    return (await AsyncStorage.getItem(KEY)) ?? '';
  } catch {
    return '';
  }
}

export async function clearPendingReferralCode(): Promise<void> {
  try {
    await AsyncStorage.removeItem(KEY);
  } catch {
    // best-effort
  }
}

async function remember(url: string | null | undefined): Promise<void> {
  const code = parseReferralCode(url);
  if (!code) return;
  try {
    await AsyncStorage.setItem(KEY, code);
  } catch {
    // best-effort
  }
}

/** Start listening for invite links (cold start + while running). Returns a stopper. */
export function startReferralCapture(): () => void {
  void Linking.getInitialURL().then(remember).catch(() => undefined);
  const sub = Linking.addEventListener('url', (event) => {
    void remember(event.url);
  });
  return () => sub.remove();
}
