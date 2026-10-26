/** Canonical origin for every public SEO page, the sitemap and JSON-LD. */
export const SITE_URL = "https://app.fantasygmlab.com";

/** ISR window for every SEO page: values refresh daily. */
export const SEO_REVALIDATE_SECONDS = 86400;

export function absoluteUrl(path: string): string {
  return `${SITE_URL}${path.startsWith("/") ? path : `/${path}`}`;
}

export const SEO_POSITIONS = ["qb", "rb", "wr", "te"] as const;
export type SeoPosition = (typeof SEO_POSITIONS)[number];

export const POSITION_NAMES: Record<SeoPosition, { singular: string; plural: string; upper: string }> = {
  qb: { singular: "quarterback", plural: "quarterbacks", upper: "QB" },
  rb: { singular: "running back", plural: "running backs", upper: "RB" },
  wr: { singular: "wide receiver", plural: "wide receivers", upper: "WR" },
  te: { singular: "tight end", plural: "tight ends", upper: "TE" },
};

export function parsePosition(value: string): SeoPosition | null {
  const lower = value.toLowerCase();
  return (SEO_POSITIONS as readonly string[]).includes(lower) ? (lower as SeoPosition) : null;
}

export const RANKINGS_PATH = (position: SeoPosition) => `/dynasty-rankings/${position}`;
export const CHART_PATH = "/dynasty-trade-value-chart";
export const HUB_PATH = "/dynasty-tools";
export const PLAYER_PATH = (slug: string) => `/dynasty-players/${slug}`;

/** Shared 1200x630 share-preview card (public/og-image.png) for the root
 * layout and every public SEO page; absolute so no metadataBase is needed. */
export const OG_IMAGE = {
  url: "https://app.fantasygmlab.com/og-image.png",
  width: 1200,
  height: 630,
  alt: "FantasyDesk: the trade your leaguemate would actually accept",
};
