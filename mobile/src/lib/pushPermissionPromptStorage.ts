import AsyncStorage from '@react-native-async-storage/async-storage';

import { parseDismissedAt } from './pushPermissionPrompt';

const KEY = 'fgl:push-prompt-dismissed-at';

/** When the user last tapped "Not now" on the notification pre-prompt. */
export async function getPushPromptDismissedAt(): Promise<number | null> {
  try {
    return parseDismissedAt(await AsyncStorage.getItem(KEY));
  } catch {
    return null;
  }
}

export async function setPushPromptDismissedAt(at: number): Promise<void> {
  try {
    await AsyncStorage.setItem(KEY, String(at));
  } catch {
    // Best-effort: worst case the pre-prompt shows again sooner.
  }
}
