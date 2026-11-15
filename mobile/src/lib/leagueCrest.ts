// Twin file: web-next/src/lib/leagueCrest.ts and mobile/src/lib/leagueCrest.ts stay identical.
//
// The league crest: a league has no profile picture of its own in saved_leagues, so the header and the switcher draw a generated
// one: a coloured disc with the league's initials. Pure (no React, no DOM): the colour is a stable hash of the league id, so the same
// league is the same colour on web and app, in every list, forever. A real avatar URL, when a caller has one, wins over the crest.

/** "The Revivalry Dynasty Superflex League" -> "RD"; "Donk" -> "DO"; "" -> "FD". Skips filler words and numbers. */
export function leagueInitials(name: string | null | undefined): string {
  const words = (name ?? "")
    .replace(/[^\p{L}\p{N}\s'-]/gu, " ")
    .split(/\s+/)
    .filter((w) => w.length > 0 && !/^(the|of|a|an|and|league|dynasty|fantasy|football|superflex|ppr|\d+)$/i.test(w));
  if (words.length === 0) return (name ?? "").trim() ? (name ?? "").trim().slice(0, 2).toUpperCase() : "FD";
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
  return (words[0][0] + words[1][0]).toUpperCase();
}

function hash(key: string): number {
  // FNV-1a with a murmur-style finalizer: consecutive ids (Sleeper ids differ in the last digits) still land on different hues.
  let h = 2166136261;
  for (let i = 0; i < key.length; i++) {
    h ^= key.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  h ^= h >>> 13;
  h = Math.imul(h, 0x5bd1e995);
  h ^= h >>> 15;
  return h >>> 0;
}

/** Hue 0-359 for a league id (or name when there is no id). Stable. */
export function leagueCrestHue(key: string | null | undefined): number {
  return hash(key || "fantasydesk") % 360;
}

/** Fill and ink for the crest disc: a mid-light, medium-saturation fill with dark ink (readable in light and dark themes). */
export function leagueCrestColors(key: string | null | undefined): { fill: string; ink: string; ring: string } {
  const h = leagueCrestHue(key);
  return { fill: `hsl(${h} 62% 62%)`, ink: "#0b1220", ring: `hsl(${h} 70% 78%)` };
}
