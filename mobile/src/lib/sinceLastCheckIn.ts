import AsyncStorage from '@react-native-async-storage/async-storage';

const KEY_PREFIX = 'fgl:dashboard-seen-recs:';

/**
 * Mobile's take on the web app's "Since your last check-in" (What Changed /
 * Decision Memory — modules/decision_memory.py): same user-facing job (show
 * what's new since you last looked), simpler mechanism. The web version is a
 * durable, cross-cutting event log written at every recommendation
 * transition (trade ideas, waivers, etc.) with a Free/session vs.
 * Premium/durable-history split. Replicating that whole write-side pipeline
 * on mobile — hooking persist_after_transition into every recommendation
 * path — is a much larger, separate effort. This instead diffs the
 * Dashboard's own stable recommendation_ids (recommendation_lifecycle's
 * contract) against what was last seen on this device, which gets the same
 * "what's new" value at Free-tier (session-equivalent) fidelity without a
 * new backend surface. Premium's durable cross-device history isn't
 * replicated here.
 */

async function getSeenIds(leagueId: string): Promise<Set<string>> {
  try {
    const raw = await AsyncStorage.getItem(KEY_PREFIX + leagueId);
    if (!raw) return new Set();
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? new Set(parsed.filter((id) => typeof id === 'string')) : new Set();
  } catch {
    return new Set();
  }
}

async function setSeenIds(leagueId: string, ids: string[]): Promise<void> {
  try {
    await AsyncStorage.setItem(KEY_PREFIX + leagueId, JSON.stringify(ids.slice(0, 100)));
  } catch {
    // Best-effort only — a storage failure just means every item looks "new" next time.
  }
}

/**
 * Compares `currentRecommendationIds` against what was stored for this
 * league on a previous call, returns the ones that are new, then persists
 * the current set for next time. Call once per Dashboard load.
 */
export async function diffAndRecordSeen(
  leagueId: string,
  currentRecommendationIds: string[],
): Promise<{ newIds: Set<string>; isFirstVisit: boolean }> {
  const ids = currentRecommendationIds.filter(Boolean);
  const seen = await getSeenIds(leagueId);
  const isFirstVisit = seen.size === 0;
  const newIds = isFirstVisit ? new Set<string>() : new Set(ids.filter((id) => !seen.has(id)));
  await setSeenIds(leagueId, ids);
  return { newIds, isFirstVisit };
}
