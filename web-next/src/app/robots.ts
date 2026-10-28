import type { MetadataRoute } from "next";

import { SITE_URL } from "@/lib/seo/site";

export default function robots(): MetadataRoute.Robots {
  return {
    sitemap: `${SITE_URL}/sitemap.xml`,
    rules: {
      userAgent: "*",
      allow: "/",
      disallow: ["/dashboard", "/portfolio", "/design", "/sample-league", "/api/"],
    },
  };
}
