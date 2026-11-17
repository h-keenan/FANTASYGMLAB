// Shared (web + mobile twin, byte-identical, import-free): the ONE fallback chain behind every player picture.
//
//   1. real headshot (Sleeper id)           -- skipped for generated/made-up players (no id)
//   2. team logo                            -- team defenses only (their Sleeper "player id" is the team code)
//   3. monogram: initials on the position colour -- always available, never an empty or black circle
//
// A source that fails to load is recorded by its `key`; `pickAvatarSource` then returns the next one. The monogram can
// not fail, so the chain always ends on something visible.

export const SLEEPER_HEADSHOT_BASE = "https://sleepercdn.com/content/nfl/players";
export const SLEEPER_TEAM_LOGO_BASE = "https://sleepercdn.com/images/team_logos/nfl";

export type AvatarSource =
  | { kind: "headshot"; key: string; url: string }
  | { kind: "teamLogo"; key: string; url: string }
  | { kind: "monogram"; key: string; label: string; position: string | null };

export interface AvatarFallbackInput {
  playerId?: string | null;
  name?: string | null;
  /** Caller-supplied initials / code; wins over initials derived from `name`. */
  label?: string | null;
  position?: string | null;
  team?: string | null;
}

const DEFENSE_POSITIONS = new Set(["DEF", "DST", "D/ST", "DEFENSE"]);

export function isDefensePosition(position: string | null | undefined): boolean {
  return !!position && DEFENSE_POSITIONS.has(position.toUpperCase());
}

/** "Ja'Marr Chase" -> "JC"; one word -> first two letters; nothing usable -> "?". */
export function monogramFromName(name: string | null | undefined): string {
  const words = (name ?? "")
    .replace(/[.,]/g, " ")
    .split(/\s+/)
    .filter((w) => w && !/^(jr|sr|ii|iii|iv|v)$/i.test(w));
  if (words.length === 0) return "?";
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
  return (words[0][0] + words[words.length - 1][0]).toUpperCase();
}

/** The label drawn in the monogram: the caller's label, else initials from the name, else the team code, else "?". */
export function avatarMonogram(input: AvatarFallbackInput): string {
  const label = input.label?.trim();
  if (label) return label;
  if (input.name?.trim()) return monogramFromName(input.name);
  if (input.team?.trim()) return input.team.trim().toUpperCase().slice(0, 3);
  return "?";
}

export function teamLogoUrl(team: string | null | undefined): string | null {
  const code = (team ?? "").trim().toLowerCase();
  return /^[a-z]{2,4}$/.test(code) ? `${SLEEPER_TEAM_LOGO_BASE}/${code}.png` : null;
}

/** Every source this player can try, best first. Always ends with the monogram. */
export function avatarChain(input: AvatarFallbackInput): AvatarSource[] {
  const chain: AvatarSource[] = [];
  const id = input.playerId?.trim() || null;
  const defense = isDefensePosition(input.position);
  // A defense's Sleeper id is its team code, which has no headshot, so it goes straight to the logo.
  if (id && !defense) chain.push({ kind: "headshot", key: `headshot:${id}`, url: `${SLEEPER_HEADSHOT_BASE}/${id}.jpg` });
  if (defense) {
    const logo = teamLogoUrl(input.team ?? id);
    if (logo) chain.push({ kind: "teamLogo", key: `logo:${logo}`, url: logo });
  }
  chain.push({ kind: "monogram", key: "monogram", label: avatarMonogram(input), position: input.position ?? null });
  return chain;
}

/** First source that has not already failed to load. The monogram never fails, so this always returns one. */
export function pickAvatarSource(input: AvatarFallbackInput, failedKeys: readonly string[]): AvatarSource {
  const chain = avatarChain(input);
  return chain.find((s) => s.kind === "monogram" || !failedKeys.includes(s.key)) ?? chain[chain.length - 1];
}
