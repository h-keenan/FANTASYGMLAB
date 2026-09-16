import { Platform } from 'react-native';
import Constants from 'expo-constants';
import * as Device from 'expo-device';
import * as Notifications from 'expo-notifications';

import { api } from './api';

/**
 * Expo's managed push service (not raw APNs/FCM handling) — idiomatic for an
 * Expo-managed app. Every step here fails soft: push is an enrichment, never
 * something that should block sign-in, sign-out, or app startup.
 */

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowBanner: true,
    shouldShowList: true,
    shouldPlaySound: false,
    shouldSetBadge: false,
  }),
});

let lastRegisteredToken: string | null = null;

function projectId(): string | null {
  const id =
    Constants.expoConfig?.extra?.eas?.projectId ??
    (Constants as unknown as { easConfig?: { projectId?: string } }).easConfig?.projectId;
  return typeof id === 'string' && id ? id : null;
}

async function getExpoPushToken(): Promise<string | null> {
  if (!Device.isDevice) {
    // Simulators/emulators can't receive real push notifications.
    return null;
  }
  const id = projectId();
  if (!id) {
    console.warn(
      '[push] No EAS project ID configured (app.json extra.eas.projectId) — skipping push token registration.',
    );
    return null;
  }
  try {
    const { data } = await Notifications.getExpoPushTokenAsync({ projectId: id });
    return data;
  } catch (err) {
    console.warn('[push] Failed to fetch Expo push token', err);
    return null;
  }
}

async function ensurePermission(): Promise<boolean> {
  const existing = await Notifications.getPermissionsAsync();
  if (existing.granted) return true;
  const requested = await Notifications.requestPermissionsAsync();
  return requested.granted;
}

async function ensureAndroidChannel(): Promise<void> {
  if (Platform.OS !== 'android') return;
  await Notifications.setNotificationChannelAsync('default', {
    name: 'default',
    importance: Notifications.AndroidImportance.DEFAULT,
  });
}

/** Request permission, mint an Expo push token, and register it with our backend. */
export async function syncPushToken(): Promise<void> {
  try {
    await ensureAndroidChannel();
    const granted = await ensurePermission();
    if (!granted) return;
    const token = await getExpoPushToken();
    if (!token) return;
    await api.registerPushToken(token, Platform.OS);
    lastRegisteredToken = token;
  } catch (err) {
    console.warn('[push] syncPushToken failed', err);
  }
}

/** Unregister this device's token — called on sign-out so a shared/reused
 * device doesn't keep delivering pushes meant for the previous account. */
export async function unregisterCurrentPushToken(): Promise<void> {
  const token = lastRegisteredToken;
  if (!token) return;
  lastRegisteredToken = null;
  try {
    await api.unregisterPushToken(token);
  } catch (err) {
    console.warn('[push] unregisterCurrentPushToken failed', err);
  }
}
