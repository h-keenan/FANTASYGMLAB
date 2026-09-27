/**
 * Pure name-shortening logic shared by any component that needs to degrade a
 * full player name to "F. Lastname" instead of a raw character-truncated
 * ellipsis (coridian_: "Jauan Jenni…" on Trade Hub's cards should instead
 * read "J. Jennings").
 *
 * Deliberately dumb about *when* to shorten — that decision belongs to the
 * caller (see PlayerNameText's onTextLayout-based clip detection, which only
 * invokes this once a name has actually failed to fit its real rendered
 * width, rather than guessing from a character-count threshold that would
 * shorten names that would've fit fine in a wider consumer). This function
 * only answers "given that we need to shorten, what's the right string?".
 *
 * "Last name" is everything after the first whitespace-separated token, not
 * just the final word — so multi-word surnames ("St. Brown") and suffixes
 * ("Jr.", "Sr.", "II", "III", "IV") stay attached to the last name rather
 * than being dropped or treated as a separate unit, matching how this
 * codebase already stores/displays full names as a single string with no
 * separate suffix field (see modules/rankings.py name handling).
 */
export function abbreviatePlayerName(name: string | null | undefined): string {
  if (!name) return '';
  const trimmed = name.trim();
  if (!trimmed) return '';
  const parts = trimmed.split(/\s+/);
  // Single-word names (mononyms) have no "first name" to shrink to an
  // initial — return as-is rather than producing "N." with nothing after it.
  if (parts.length < 2) return trimmed;
  return `${parts[0][0]}. ${parts.slice(1).join(' ')}`;
}
