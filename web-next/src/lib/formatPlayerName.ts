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
