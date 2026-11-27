import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { AppCta, SeoPageShell } from "@/components/seo/SeoChrome";
import { ValueTable } from "@/components/seo/ValueTable";
import { loadChartRows } from "@/lib/seo/chartRows";
import { itemListLd, webPageLd } from "@/lib/seo/jsonld";
import { absoluteUrl, CHART_PATH, PLAYER_PATH, OG_IMAGE } from "@/lib/seo/site";

// Optional catch-all with no build-time params: lets the page be generated on
// first request (the value API may not be reachable during `next build`) while
// still being ISR-cached. Any extra path segment is a 404.
export const revalidate = 86400; // daily ISR (segment config must be a literal)
export const dynamicParams = true;
export function generateStaticParams() {
  return [];
}

const TITLE = "Dynasty Trade Value Chart: 1QB and Superflex Player Values";
const DESCRIPTION =
  "Dynasty trade value chart with the top 100 players valued for 1QB and Superflex leagues, including age and workload trend. Updated daily from FantasyDesk.";

export async function generateMetadata({ params }: { params: Promise<{ view?: string[] }> }): Promise<Metadata> {
  if ((await params).view?.length) return { robots: { index: false, follow: false } };
  const url = absoluteUrl(CHART_PATH);
  return {
    title: TITLE,
    description: DESCRIPTION,
    alternates: { canonical: url },
    openGraph: { title: TITLE, description: DESCRIPTION, url, type: "website", siteName: "FantasyDesk", images: [OG_IMAGE] },
    twitter: { card: "summary_large_image", title: TITLE, description: DESCRIPTION, images: [OG_IMAGE.url] },
  };
}

export default async function TradeValueChartPage({ params }: { params: Promise<{ view?: string[] }> }) {
  if ((await params).view?.length) notFound();
  const chart = await loadChartRows();
  if (!chart) notFound();
  const { rows, updated, updatedAt } = chart;

  return (
    <SeoPageShell
      crumbs={[
        { name: "FantasyDesk", path: "/" },
        { name: "Dynasty tools", path: "/dynasty-tools" },
        { name: "Trade value chart", path: CHART_PATH },
      ]}
      kicker="Trade values"
      title={TITLE}
      intro="Both formats side by side. The main value column is for 1QB leagues; the Superflex column re-values every player for leagues that start a second quarterback, so you can see how much quarterbacks move."
      updated={updated}
      jsonLd={[
        webPageLd({ name: TITLE, description: DESCRIPTION, path: CHART_PATH, dateModified: updatedAt }),
        itemListLd({
          name: TITLE,
          path: CHART_PATH,
          items: rows.map((r) => ({ name: r.player.name, path: r.slug ? PLAYER_PATH(r.slug) : undefined })),
        }),
      ]}
    >
      <ValueTable rows={rows} valueHeader="1QB value" extraHeader="Superflex" caption="Dynasty trade value chart" />
      <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
        Ranks are 1QB overall ranks; the number under each Superflex value is that player&apos;s Superflex overall
        rank. Values assume a 12-team PPR league and are not tied to any specific league.
      </p>
      <AppCta
        title="Check a trade against your own roster"
        body="A generic chart can't see your team. FantasyDesk values both sides of a trade for your league's settings and your roster needs, then gives a verdict."
      />
    </SeoPageShell>
  );
}
