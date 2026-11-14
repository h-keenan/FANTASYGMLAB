/**
 * Player-name display rule (owner decision): wherever a name would be
 * truncated, show the first initial plus the WHOLE surname
 * ("Saquon Barkley" -> "S. Barkley"), keeping any suffix with the surname
 * ("Michael Penix Jr." -> "M. Penix Jr."). Only if that still does not fit
 * does the caller fall back to an ellipsis on the surname.
 *
 * Pure and dependency-free. Byte-identical twin at
 * mobile/src/lib/playerNameDisplay.ts (registered IDENTICAL in
 * scripts/check_lib_twins.mjs). Used by the PlayerName component on both
 * platforms and by width-bound share cards.
 */

export type PlayerNameParts = {
  /** Given name as written ("Saquon", "T.J.", "Amon-Ra"); "" for mononyms. */
  first: string;
  /** Surname without the suffix ("St. Brown", "Smith-Njigba"). */
  surname: string;
  /** Generational suffix ("Jr.", "III"), "" when absent. */
  suffix: string;
  /** True for a single-token name or a team defense ("Ravens D/ST"). */
  whole: boolean;
  /** True when `first` is already initials ("T.J.", "C.J.", "J.") or an all-caps initialism ("CJ"). */
  firstIsInitials: boolean;
};

const SUFFIX_RE = /^(?:jr|sr|ii|iii|iv|v|vi)\.?$/i;
// Team defense labels never have a "first name": "Ravens D/ST", "49ers DEF".
const TEAM_DEF_RE = /(?:^|\s)(?:d\/st|dst|def|defense)$/i;
const INITIALS_RE = /^(?:\p{L}\.){1,4}$/u;
const INITIALISM_RE = /^\p{Lu}{2,3}$/u;

/** First user-perceived letter (code point plus any combining marks). */
function leadingLetter(token: string): string {
  const match = token.match(/^[\p{L}\p{N}][\p{M}]*/u);
  return match ? match[0] : Array.from(token)[0] ?? "";
}

export function splitPlayerName(full: string | null | undefined): PlayerNameParts {
  const trimmed = (full ?? "").replace(/\s+/g, " ").trim();
  if (!trimmed) return { first: "", surname: "", suffix: "", whole: true, firstIsInitials: false };
  const tokens = trimmed.split(" ");
  if (tokens.length < 2 || TEAM_DEF_RE.test(trimmed)) {
    return { first: "", surname: trimmed, suffix: "", whole: true, firstIsInitials: false };
  }
  let suffix = "";
  let body = tokens;
  // "Jr." only counts as a suffix when something remains for the surname.
  if (body.length > 2 && SUFFIX_RE.test(body[body.length - 1])) {
    suffix = body[body.length - 1];
    body = body.slice(0, -1);
  }
  const [first, ...rest] = body;
  const firstIsInitials = INITIALS_RE.test(first) || INITIALISM_RE.test(first);
  return { first, surname: rest.join(" "), suffix, whole: false, firstIsInitials };
}

/** "Saquon Barkley" -> "S. Barkley"; never touches names that cannot shrink. */
export function shortPlayerName(full: string | null | undefined): string {
  const parts = splitPlayerName(full);
  if (parts.whole) return parts.surname;
  const tail = parts.suffix ? `${parts.surname} ${parts.suffix}` : parts.surname;
  // "T.J.", "C.J.", "CJ" are the player's real identity: keep them whole.
  if (parts.firstIsInitials) return `${parts.first} ${tail}`;
  return `${leadingLetter(parts.first)}. ${tail}`;
}

/**
 * Pre-shortened name for width-bound surfaces that cannot measure (Satori
 * share cards): the full name up to `maxChars`, otherwise the short form.
 */
export function fitPlayerName(full: string | null | undefined, maxChars: number): string {
  const trimmed = (full ?? "").replace(/\s+/g, " ").trim();
  return trimmed.length > maxChars ? shortPlayerName(trimmed) : trimmed;
}

/**
 * The surname alone, for the few strings that have no room for an initial ("Draft Brisker", "Gibbs, Chase, Metcalf").
 * Suffixes are dropped ("Penix Jr." -> "Penix", never the "Jr." that `split(" ").pop()` returned) and multi-word
 * surnames stay whole ("St. Brown"). A mononym or team defense is returned as is.
 */
export function playerSurname(full: string | null | undefined): string {
  return splitPlayerName(full).surname;
}
