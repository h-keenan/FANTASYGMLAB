import type { PublicPlayer } from "./publicValues";

/** URL-safe slug from a display name: "Ja'Marr Chase" -> "jamarr-chase". */
export function slugify(name: string): string {
  return name
    .normalize("NFKD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/['’.]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

/**
 * Stable slug per player id. Names that collide inside the given list get the
 * Sleeper player id appended (to every colliding player, so the result does
 * not depend on list order). A name that slugifies to nothing gets no slug.
 */
export function assignSlugs(players: readonly Pick<PublicPlayer, "player_id" | "name">[]): Map<string, string> {
  const bySlug = new Map<string, string[]>();
  for (const player of players) {
    const slug = slugify(player.name);
    if (!slug) continue;
    bySlug.set(slug, [...(bySlug.get(slug) ?? []), player.player_id]);
  }
  const result = new Map<string, string>();
  for (const [slug, ids] of bySlug) {
    for (const id of ids) result.set(id, ids.length > 1 ? `${slug}-${id}` : slug);
  }
  return result;
}

export function findPlayerBySlug<T extends Pick<PublicPlayer, "player_id" | "name">>(
  players: readonly T[],
  slug: string,
): T | null {
  const slugs = assignSlugs(players);
  return players.find((player) => slugs.get(player.player_id) === slug) ?? null;
}
