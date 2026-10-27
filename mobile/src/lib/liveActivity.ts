import { NativeModules, Platform } from 'react-native';

import { api } from './api';
import { getLastLeague } from './lastLeague';
import {
  parseLiveActivitiesFlag,
  planLiveActivityAction,
  toContentState,
  toWidgetSnapshot,
  type LiveActivityContentState,
} from './liveActivityCore';

/**
 * iOS-only (ActivityKit/WidgetKit). Android parity exception: see
 * docs/live-activities-widgets-plan.md. Ships DARK twice over: the JS flag
 * (EXPO_PUBLIC_LIVE_ACTIVITIES_ENABLED) AND the native module, which only
 * exists in builds prebuilt with FANTASYDESK_LIVE_ACTIVITIES=1.
 */

interface NativeLiveActivity {
  isSupported(): Promise<boolean>;
  startOrUpdate(leagueName: string, state: LiveActivityContentState): Promise<boolean>;
  end(): Promise<boolean>;
  setWidgetSnapshot(json: string): Promise<boolean>;
}

const native: NativeLiveActivity | undefined =
  Platform.OS === 'ios' ? (NativeModules.FantasyDeskLiveActivity as NativeLiveActivity | undefined) : undefined;

export const liveActivitiesEnabled = parseLiveActivitiesFlag(process.env.EXPO_PUBLIC_LIVE_ACTIVITIES_ENABLED);

let running = false;

/** One sync pass: start / update / end the Live Activity and refresh the widget. Never throws. */
export async function syncLiveActivity(isGuest: boolean): Promise<void> {
  if (!native || !liveActivitiesEnabled) return;
  try {
    const league = await getLastLeague();
    if (!league || isGuest) {
      if (running) await native.end();
      running = false;
      return;
    }
    if (!(await native.isSupported())) return;

    const [snapshot, alerts] = await Promise.all([
      api.getLiveActivity(league.leagueId).catch(() => null),
      api.getLeagueAlerts(league.leagueId, 10).catch(() => null),
    ]);

    if (alerts) {
      await native.setWidgetSnapshot(JSON.stringify(toWidgetSnapshot(league.leagueName, alerts.items, Date.now())));
    }

    const action = planLiveActivityAction(snapshot, running, { enabled: true, isGuest });
    if (action === 'start' || action === 'update') {
      const state = snapshot ? toContentState(snapshot) : null;
      if (state) running = await native.startOrUpdate(league.leagueName, state);
    } else if (action === 'end') {
      await native.end();
      running = false;
    }
  } catch {
    // Best-effort surface; never affects the app.
  }
}

export async function endLiveActivity(): Promise<void> {
  if (!native || !running) return;
  try {
    await native.end();
  } catch {
    // ignore
  }
  running = false;
}
