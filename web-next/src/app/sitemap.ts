import type { MetadataRoute } from "next";

import legalContent from "@/data/legalContent.json";
import { isPageEligible } from "@/lib/seo/content";
import { fetchBoard } from "@/lib/seo/publicValues";
import { CHART_PATH, HUB_PATH, PLAYER_PATH, RANKINGS_PATH, SEO_POSITIONS, SITE_URL, TRADE_ANALYZER_PUBLIC_PATH } from "@/lib/seo/site";
import { assignSlugs } from "@/lib/seo/slug";
import { fetchPlayoffSos, hasUsableSos } from "@/lib/seo/playoffSos";
import { MIN_ROOKIES, rookieRows } from "@/lib/seo/rookies";
import { playoffSosInSeason, PLAYOFF_SOS_PATH, ROOKIE_RANKINGS_PATH, rookieContentInSeason, seasonMoment } from "@/lib/seasonalLanding";

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

  // lastModified is only set when we actually know it: legal pages carry a real "last updated" date, and data
  // pages use their data's timestamp (below). Everything else omits it rather than claiming "changed just now".
  const legalUpdated = new Date(`${legalContent.lastUpdated} UTC`);
  const legalStamp = Number.isNaN(legalUpdated.getTime()) ? undefined : legalUpdated;
  const entries: MetadataRoute.Sitemap = [
    ...staticRoutes.map((path) => ({ url: `${BASE_URL}${path}` })),
    ...legalRoutes.map((path) => ({ url: `${BASE_URL}${path}`, lastModified: legalStamp })),
  ];

  // SEO pages. Positional/chart/player URLs are only listed when the value
  // board loaded and has real rows; if the API is unreachable they are simply
  // omitted (never listed as placeholders).
  entries.push({ url: `${BASE_URL}${HUB_PATH}` });
  // Static page (values load client-side), so it is listed even if the value API is down.
  entries.push({ url: `${BASE_URL}${TRADE_ANALYZER_PUBLIC_PATH}` });
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
    // Season-gated rookie page: listed only after the draft and only when the board has a real rookie class.
    if (rookieContentInSeason(seasonMoment())) {
      const superflex = await fetchBoard("superflex").catch(() => null);
      if (rookieRows(board, superflex).length >= MIN_ROOKIES) entries.push({ url: `${BASE_URL}${ROOKIE_RANKINGS_PATH}`, lastModified: stamp });
    }
  } catch {
    // Value API unavailable: ship the static entries only.
  }
  // Season-gated playoff SOS page: listed only during weeks 9-17 and only with a rated schedule (never a placeholder).
  if (playoffSosInSeason(seasonMoment())) {
    const sos = await fetchPlayoffSos();
    if (hasUsableSos(sos)) {
      const computed = new Date(sos.generated_at);
      // Day precision: the schedule/defense inputs move at most daily, the API recomputes hourly.
      const day = Number.isNaN(computed.getTime()) ? undefined : new Date(Date.UTC(computed.getUTCFullYear(), computed.getUTCMonth(), computed.getUTCDate()));
      entries.push({ url: `${BASE_URL}${PLAYOFF_SOS_PATH}`, lastModified: day });
    }
  }
  return entries;
}
