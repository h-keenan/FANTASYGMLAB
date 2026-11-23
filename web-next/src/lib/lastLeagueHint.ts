/**
 * The league the signed-in user last opened on Today, remembered on this device so a cold start of "/" can skip two
 * serial round trips (saved_leagues, then device preferences) before it knows where to go, and so the inline early-fetch
 * script can start that league's Today request while the bundle is still downloading.
 *
 * Plain (unscoped) key holding the user id inside the value, because the inline script reads it before auth loads. It is
 * listed in accountScope PURGE_UNSCOPED_KEYS, so sign-out and a user change clear it. It is only a hint: the Today page
 * clears it when that league fails to load, and every reader checks the user id.
 */
import { readProtectedReturnPath } from "@/lib/protectedRouteReturn";
import { readPendingBridge } from "@/lib/tradeBridge";

export const LAST_LEAGUE_STORAGE_KEY = "fgl.lastLeague.v1";

export interface LastLeague {
  uid: string;
  id: string;
  name: string;
}

function store(): Storage | null {
  try {
    return typeof window === "undefined" ? null : window.localStorage;
  } catch {
    return null;
  }
}

/** True when something wants a different landing than the last league (a pending analyzer trade or a protected page to return to). */
export function hasPendingLandingOverride(): boolean {
  const s = store();
  return Boolean(readPendingBridge(s) || readProtectedReturnPath(s));
}

export function readLastLeague(userId: string | null | undefined): LastLeague | null {
  if (!userId) return null;
  try {
    const parsed = JSON.parse(store()?.getItem(LAST_LEAGUE_STORAGE_KEY) ?? "null") as Partial<LastLeague> | null;
    if (!parsed || parsed.uid !== userId || typeof parsed.id !== "string" || !parsed.id) return null;
    return { uid: userId, id: parsed.id, name: typeof parsed.name === "string" ? parsed.name : "" };
  } catch {
    return null;
  }
}

export function writeLastLeague(userId: string, id: string, name: string): void {
  try {
    const prev = readLastLeague(userId);
    if (prev && prev.id === id && prev.name === name) return;
    store()?.setItem(LAST_LEAGUE_STORAGE_KEY, JSON.stringify({ uid: userId, id, name } satisfies LastLeague));
  } catch {
    /* storage unavailable */
  }
}

export function clearLastLeague(id: string): void {
  try {
    const s = store();
    const parsed = JSON.parse(s?.getItem(LAST_LEAGUE_STORAGE_KEY) ?? "null") as Partial<LastLeague> | null;
    if (parsed?.id === id) s?.removeItem(LAST_LEAGUE_STORAGE_KEY);
  } catch {
    /* ignore */
  }
}
