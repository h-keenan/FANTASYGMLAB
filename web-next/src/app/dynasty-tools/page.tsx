import type { Metadata } from "next";
import Link from "next/link";

import { AppCta, SeoPageShell } from "@/components/seo/SeoChrome";
import { itemListLd, webPageLd } from "@/lib/seo/jsonld";
import { absoluteUrl, CHART_PATH, HUB_PATH, POSITION_NAMES, RANKINGS_PATH, SEO_POSITIONS } from "@/lib/seo/site";

export const revalidate = 86400; // daily ISR (segment config must be a literal)

const TITLE = "Dynasty Fantasy Football Tools: Rankings and Trade Value Chart";
const DESCRIPTION =
  "Free dynasty fantasy football tools from FantasyDesk: positional dynasty rankings, a 1QB and Superflex trade value chart, and player value pages, refreshed daily.";

export const metadata: Metadata = {
  title: TITLE,
  description: DESCRIPTION,
  alternates: { canonical: absoluteUrl(HUB_PATH) },
  openGraph: { title: TITLE, description: DESCRIPTION, url: absoluteUrl(HUB_PATH), type: "website", siteName: "FantasyDesk" },
  twitter: { card: "summary", title: TITLE, description: DESCRIPTION },
};

const TOOLS = [
  ...SEO_POSITIONS.map((p) => ({
    href: RANKINGS_PATH(p),
    name: `Dynasty ${POSITION_NAMES[p].upper} rankings`,
    blurb: `The top ${POSITION_NAMES[p].plural} by dynasty value, with age and workload trend. Each name links to a player value page.`,
  })),
  {
    href: CHART_PATH,
    name: "Dynasty trade value chart",
    blurb: "The top 100 players with 1QB and Superflex values side by side.",
  },
  {
    href: "/methodology",
    name: "How we value players",
    blurb: "What goes into a FantasyDesk dynasty value: market prices, age, production and role.",
  },
];

export default function DynastyToolsHub() {
  return (
    <SeoPageShell
      crumbs={[
        { name: "FantasyDesk", path: "/" },
        { name: "Dynasty tools", path: HUB_PATH },
      ]}
      kicker="Dynasty tools"
      title={TITLE}
      intro="Every page here is built from the same player values FantasyDesk uses inside the app, for a default 12-team PPR dynasty league, and is refreshed once a day."
      jsonLd={[
        webPageLd({ name: TITLE, description: DESCRIPTION, path: HUB_PATH }),
        itemListLd({ name: TITLE, path: HUB_PATH, items: TOOLS.map((t) => ({ name: t.name, path: t.href })) }),
      ]}
    >
      <ul className="flex flex-col gap-3">
        {TOOLS.map((tool) => (
          <li key={tool.href} className="glass-surface flex flex-col gap-1 p-4">
            <Link href={tool.href} className="text-base font-bold underline" style={{ color: "var(--color-accent)" }}>
              {tool.name}
            </Link>
            <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
              {tool.blurb}
            </p>
          </li>
        ))}
      </ul>
      <AppCta
        title="Make it specific to your league"
        body="These tools use default settings. Connect your Sleeper league and FantasyDesk values every player for your scoring and roster, then recommends trades and waiver moves."
      />
    </SeoPageShell>
  );
}
