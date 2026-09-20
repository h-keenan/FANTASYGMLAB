import AsyncStorage from '@react-native-async-storage/async-storage';

import type { DashboardResponse } from './api';

const KEY_PREFIX = 'fgl:dashboard-cache:';

/**
 * Last-known-good Dashboard response per league, purely a perceived-
 * performance aid: the backend does real per-request computation (roster
 * pull, lineup optimization, trade/waiver search) and can legitimately take
 * a few seconds, especially on a cold instance. Showing the previous
 * result instantly while a fresh one loads in the background means the
 * screen never reads as "stuck" — it's never a substitute for the live
 * fetch, which always still runs and overwrites this the moment it
 * resolves. Best-effort only: any storage failure just means no cache hit,
 * never a crash.
 */
export async function getCachedDashboard(leagueId: string): Promise<DashboardResponse | null> {
  try {
    const raw = await AsyncStorage.getItem(`${KEY_PREFIX}${leagueId}`);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (parsed && parsed.ok === true && Array.isArray(parsed.items)) {
      return parsed as DashboardResponse;
    }
    return null;
  } catch {
    return null;
  }
}

export async function setCachedDashboard(leagueId: string, data: DashboardResponse): Promise<void> {
  try {
    await AsyncStorage.setItem(`${KEY_PREFIX}${leagueId}`, JSON.stringify(data));
  } catch {
    // Best-effort only.
  }
}
