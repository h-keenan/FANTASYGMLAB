import type { MetadataRoute } from "next";

import legalContent from "@/data/legalContent.json";
import { isPageEligible } from "@/lib/seo/content";
import { fetchBoard } from "@/lib/seo/publicValues";
import { CHART_PATH, HUB_PATH, PLAYER_PATH, RANKINGS_PATH, SEO_POSITIONS, SITE_URL } from "@/lib/seo/site";
import { assignSlugs } from "@/lib/seo/slug";

// Only the genuinely public, non-league-specific static routes — every
// [leagueId] route and /dashboard/portfolio (user-specific, already
// disallowed in robots.ts) are deliberately left out.
const BASE_URL = SITE_URL;

// Rendered per request (the fetch below is itself cached for a day), so a
// build with no reachable API never freezes an SEO-less sitemap.
export const dynamic = "force-dynamic";

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const staticRoutes = ["", "/premium", "/news", "/college-scouting", "/trade-history", "/methodology"];
  const legalRoutes = Object.keys(legalContent.pages).map((pageKey) => `/legal/${pageKey}`);

  const entries: MetadataRoute.Sitemap = [...staticRoutes, ...legalRoutes].map((path) => ({
    url: `${BASE_URL}${path}`,
    lastModified: new Date(),
  }));

  // SEO pages. Positional/chart/player URLs are only listed when the value
  // board loaded and has real rows; if the API is unreachable they are simply
  // omitted (never listed as placeholders).
  entries.push({ url: `${BASE_URL}${HUB_PATH}` });
  try {
    const board = await fetchBoard("1qb");
    const lastModified = new Date(board.source_updated_at);
    const stamp = Number.isNaN(lastModified.getTime()) ? undefined : lastModified;
    for (const position of SEO_POSITIONS) {
      entries.push({ url: `${BASE_URL}${RANKINGS_PATH(position)}`, lastModified: stamp });
    }
    entries.push({ url: `${BASE_URL}${CHART_PATH}`, lastModified: stamp });
    const eligible = board.players.filter(isPageEligible);
    const slugs = assignSlugs(eligible);
    for (const player of eligible) {
      const slug = slugs.get(player.player_id);
      if (slug) entries.push({ url: `${BASE_URL}${PLAYER_PATH(slug)}`, lastModified: stamp });
    }
  } catch {
    // Value API unavailable: ship the static entries only.
  }
  return entries;
}
