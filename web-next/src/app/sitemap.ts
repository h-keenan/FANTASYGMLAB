import type { MetadataRoute } from "next";

import legalContent from "@/data/legalContent.json";

// Only the genuinely public, non-league-specific static routes — every
// [leagueId] route and /dashboard/portfolio (user-specific, already
// disallowed in robots.ts) are deliberately left out.
const BASE_URL = "https://app.fantasygmlab.com";

export default function sitemap(): MetadataRoute.Sitemap {
  const staticRoutes = ["", "/premium", "/news", "/college-scouting", "/trade-history"];
  const legalRoutes = Object.keys(legalContent.pages).map((pageKey) => `/legal/${pageKey}`);

  return [...staticRoutes, ...legalRoutes].map((path) => ({
    url: `${BASE_URL}${path}`,
    lastModified: new Date(),
  }));
}
