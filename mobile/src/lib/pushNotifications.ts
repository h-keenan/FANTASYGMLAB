import { Platform } from 'react-native';
import Constants from 'expo-constants';
import * as Device from 'expo-device';
import * as Notifications from 'expo-notifications';
import { StackActions } from '@react-navigation/routers';

import { api } from './api';
import { navigationRef } from '../navigation/navigationRef';

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

/**
 * Every push category (see modules/push_triggers.py) attaches
 * {league_id, league_name, category} as `data`. Tapping any of them lands
 * on that league's hub for now — specific per-category destinations (e.g.
 * Waivers for a waiver alert) can be added here as real routing needs come
 * up without changing what the backend sends.
 */
function routeNotificationTap(data: unknown): void {
  if (!data || typeof data !== 'object') return;
  const payload = data as Record<string, unknown>;
  const leagueId = typeof payload.league_id === 'string' ? payload.league_id : '';
  const leagueName = typeof payload.league_name === 'string' ? payload.league_name : '';
  if (!leagueId || !navigationRef.isReady()) return;
  navigationRef.dispatch(StackActions.popTo('LeagueDetail', { leagueId, leagueName }));
}

/**
 * Registers the tap handler once at app startup (App.tsx) — best-effort,
 * a routing failure should never crash the app, just leave the user on
 * whatever screen they were already on.
 */
export function registerNotificationTapHandler(): () => void {
  const subscription = Notifications.addNotificationResponseReceivedListener((response) => {
    try {
      routeNotificationTap(response.notification.request.content.data);
    } catch (err) {
      console.warn('[push] routeNotificationTap failed', err);
    }
  });
  // Cold start: the app was launched BY tapping a notification, so no
  // "response received" event fires for it — this covers that case.
  Notifications.getLastNotificationResponseAsync()
    .then((response) => {
      if (response) routeNotificationTap(response.notification.request.content.data);
    })
    .catch(() => {});
  return () => subscription.remove();
}
