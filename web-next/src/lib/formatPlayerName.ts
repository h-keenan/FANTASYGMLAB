/**
 * "F. Lastname" player-name shortening. Byte-for-byte the same logic as
 * mobile/src/lib/formatPlayerName.ts (abbreviatePlayerName); both are pinned
 * by the identical fixture list in playerNameFixtures.ts.
 *
 * "Last name" is everything after the first whitespace-separated token, so
 * multi-word surnames ("St. Brown") and suffixes ("Jr.", "III") stay attached.
 * A first name that is already initials ("D.K.", "A.J.") or an all-caps
 * initialism ("CJ", "DJ") is kept whole. Never character-truncates.
 */
export function abbreviatePlayerName(name: string | null | undefined): string {
  if (!name) return "";
  const trimmed = name.trim();
  if (!trimmed) return "";
  const parts = trimmed.split(/\s+/);
  // Single-word names (mononyms) have no first name to shrink to an initial.
  if (parts.length < 2) return trimmed;
  const [first, ...rest] = parts;
  // A first name that is already initials ("D.K.", "A.J.", "J.") or an
  // all-caps initialism ("CJ", "DJ", "TJ") is the player's real identity:
  // keep it whole instead of collapsing it to a misleading single letter.
  if (/^(?:\p{L}\.){1,3}$/u.test(first) || /^\p{Lu}{2,3}$/u.test(first)) return trimmed;
  const initial = Array.from(first)[0];
  return `${initial}. ${rest.join(" ")}`;
}

/**
 * Ported from mobile/src/lib/formatPlayerName.ts (same threshold, same
 * decision). The mobile calibration: 12 is the narrowest real container
 * (Trade Hub exchange chips at 375pt, ~76pt of usable name width at a 14.5pt
 * bold name, ~10 characters fit) plus a couple characters of headroom, so
 * short names ("Josh Allen", "CeeDee Lamb") stay full while every name seen
 * truncating in production ("Juwan Johnson", "Rhamondre Stevenson") is caught
 * before the first frame. Wide web layouts pass `threshold={Infinity}` to
 * PlayerNameText and rely on measured overflow instead.
 */
export const PLAYER_NAME_LENGTH_THRESHOLD = 12;

export function shouldAbbreviatePlayerName(
  name: string | null | undefined,
  threshold: number = PLAYER_NAME_LENGTH_THRESHOLD,
): boolean {
  if (!name) return false;
  const trimmed = name.trim();
  if (!trimmed) return false;
  return trimmed.length > threshold;
}
