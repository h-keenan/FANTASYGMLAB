/**
 * Up to two upper-case initials for a team or user name, used when there is no
 * avatar picture. Works on code points, not UTF-16 units: a name that ends in an
 * emoji ("Gridiron Goats 🐐") used to produce half a surrogate pair, which
 * renders as a broken glyph and differs between server and client HTML (a
 * hydration mismatch). Names with no letters or digits at all give "".
 */
export function teamInitials(name: string | null | undefined): string {
  const parts = (name ?? "")
    .trim()
    .split(/\s+/)
    .filter((part) => /[\p{L}\p{N}]/u.test(part));
  if (parts.length === 0) return "";
  const letters = (part: string) => Array.from(part).filter((char) => /[\p{L}\p{N}]/u.test(char));
  if (parts.length === 1) return letters(parts[0]).slice(0, 2).join("").toUpperCase();
  return (letters(parts[0])[0] + letters(parts[parts.length - 1])[0]).toUpperCase();
}
