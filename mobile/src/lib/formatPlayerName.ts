/**
 * Pure name-shortening logic shared by any component that needs to degrade a
 * full player name to "F. Lastname" instead of a raw character-truncated
 * ellipsis (coridian_: "Jauan Jenni…" on Trade Hub's cards should instead
 * read "J. Jennings").
 *
 * `abbreviatePlayerName` is deliberately dumb about *when* to shorten — it
 * only answers "given that we need to shorten, what's the right string?".
 * The "when" lives in `shouldAbbreviatePlayerName` below, a deterministic
 * length-threshold decision (see its own doc comment for why a fixed
 * character count replaced the original onTextLayout-only detection).
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

/**
 * Deterministic "does this name need PlayerNameText's abbreviated form"
 * decision, answerable on first render with no layout callback round-trip.
 *
 * Replaces onTextLayout-only clip detection (see PlayerNameText), which
 * turned out to be unreliable in production — screenshots showed multiple
 * different names simultaneously still rendering truncated mid-word
 * ("Juwan John…", "Jadari…", "Wan'Dale Ro…") in the same render, which is
 * not what a one-frame detection race looks like; the RN layout-event path
 * just wasn't firing reliably across RN/Hermes versions and layout
 * contexts. A character-length threshold is deterministic: the same name
 * always produces the same decision, with no dependency on a platform
 * layout callback at all.
 *
 * THRESHOLD is calibrated to the narrowest real container this component
 * renders in: Trade Hub's exchange columns (ExchangeAssetList inside
 * TradeHubScreen -> PlayerIdentityRow -> PlayerNameText). Walking that
 * layout's actual styles at a 375pt-wide screen (iPhone SE/13 mini, the
 * narrowest device this app still supports) —
 *   content padding 2x16 -> card padding 0 -> exchangeRow padding 2x12 ->
 *   exchangeRow's two exchangeSide columns splitting what's left after the
 *   26pt swap-icon gutter and its two 8pt gaps -> exchangeSide padding
 *   2x8 -> minus PlayerIdentityRow's 38pt avatar + 8pt gap it always
 *   reserves to the name's left
 * — leaves only ~76-77pt of usable width for the name text itself. At
 * PlayerIdentityRow's 14.5pt bold name style, SF Pro's average glyph
 * advance for mixed-case text runs roughly 7.5-8pt, so only about 10
 * characters reliably fit before the line is forced to truncate.
 * THRESHOLD=12 gives a couple of characters of headroom above that raw
 * fit-count — short real names ("Josh Allen", "Joe Burrow", "CeeDee Lamb")
 * stay full — while still reliably catching every name actually observed
 * truncating in production ("Juwan Johnson" at 13 chars, "Wan'Dale
 * Robinson" at 17, "Rhamondre Stevenson" at 19 — the name from this file's
 * own motivating report) before a single frame ever renders the
 * un-abbreviated, overflowing text.
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
