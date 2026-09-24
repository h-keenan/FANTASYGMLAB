import { Platform } from 'react-native';
import Constants from 'expo-constants';
import * as Device from 'expo-device';
import * as Notifications from 'expo-notifications';
import { StackActions } from '@react-navigation/routers';

import { api, type RankedPlayer } from './api';
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
 * Every push category (see modules/push_triggers.py) attaches at least
 * {league_id, league_name, category} as `data`. top_priority/watch items
 * sourced from a headline idea with a route_player_id, and injury items,
 * additionally carry player_id/player_name — those deep-link straight to
 * that player's Player Detail screen. recap and gm_stance_reminder (and
 * any payload missing player data) have no more-specific target than the
 * league itself, so they fall back to that league's hub, same as before.
 */
export interface PushNotificationData {
  league_id?: string;
  league_name?: string;
  category?: string;
  player_id?: string;
  player_name?: string;
}

function routeNotificationTap(data: unknown): void {
  if (!data || typeof data !== 'object' || !navigationRef.isReady()) return;
  const payload = data as PushNotificationData;
  const leagueId = typeof payload.league_id === 'string' ? payload.league_id : '';
  const leagueName = typeof payload.league_name === 'string' ? payload.league_name : '';
  if (!leagueId) return;

  const playerId = typeof payload.player_id === 'string' ? payload.player_id : '';
  if (playerId) {
    // Same lean hand-built player pattern AlertsScreen/DashboardScreen use
    // for their own player taps — Player Detail fetches everything else
    // itself from player_id, so a full player fetch isn't needed here.
    const playerName = typeof payload.player_name === 'string' ? payload.player_name : '';
    const player: RankedPlayer = {
      player_id: playerId,
      name: playerName || null,
      position: null,
      team: null,
      age: null,
      status: null,
      injury_status: null,
      tier: null,
      score: null,
      overall_rank: null,
      position_rank: null,
      rank_unavailable_reason: null,
      opportunity_label: null,
    };
    navigationRef.navigate('PlayerDetail', { player, leagueId, leagueName });
    return;
  }

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
