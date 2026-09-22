import AsyncStorage from '@react-native-async-storage/async-storage';

const KEY_PREFIX = 'fgl:trade-hub-seen:';

/**
 * How many Trade Hub ideas this device last actually looked at, per league —
 * lets GM Orb show a "something's new here" glyph on the Trade Hub row
 * (coridian_: "menu titles on the GMO should have alert glyphs to indicate
 * ... new trade ideas") without any new backend infrastructure. Trade Hub's
 * idea list has no server-side identity to diff against, so this is a plain
 * count comparison, not true per-idea dedup — a lost idea replaced by a
 * different one still reads as "new" at the same count, which is fine for a
 * glance-only glyph.
 */
export async function getSeenTradeIdeaCount(leagueId: string): Promise<number> {
  try {
    const raw = await AsyncStorage.getItem(KEY_PREFIX + leagueId);
    const parsed = raw ? Number(raw) : 0;
    return Number.isFinite(parsed) ? parsed : 0;
  } catch {
    return 0;
  }
}

export async function setSeenTradeIdeaCount(leagueId: string, count: number): Promise<void> {
  try {
    await AsyncStorage.setItem(KEY_PREFIX + leagueId, String(count));
  } catch {
    // Best-effort — worst case the glyph shows again next time.
  }
}
