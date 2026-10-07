import AsyncStorage from '@react-native-async-storage/async-storage';

const KEY_PREFIX = 'fgl:recap-opened:';

/**
 * Per-league "last recap this device actually opened" flag — same
 * AsyncStorage-flag-per-league precedent as lib/tradeHubSeen.ts (Trade
 * Hub's "new idea" glyph) and lib/sinceLastCheckIn.ts (Dashboard's "since
 * your last check-in" diff), not a new storage convention. Keyed by
 * `recap_id` (modules.league_recaps' fingerprint-based id) rather than week
 * number: a week's recap can regenerate with a new fingerprint if the
 * underlying data changes, and that should count as new content again even
 * though the week number is unchanged.
 *
 * Written from RecapScreen itself (not from each entry point) so every path
 * into the recap — Dashboard's new module, Alerts' ready card, the GM Orb
 * row, or League Overview's Storylines tap-through — all mark the same
 * "opened" state. That keeps Dashboard's module from reappearing just
 * because the recap happened to be viewed from somewhere else first.
 */
export async function getLastOpenedRecapId(leagueId: string): Promise<string | null> {
  try {
    return await AsyncStorage.getItem(KEY_PREFIX + leagueId);
  } catch {
    return null;
  }
}

export async function markRecapOpened(leagueId: string, recapId: string): Promise<void> {
  if (!recapId) return;
  try {
    await AsyncStorage.setItem(KEY_PREFIX + leagueId, recapId);
  } catch {
    // Best-effort — worst case the Dashboard module shows again next time.
  }
}
