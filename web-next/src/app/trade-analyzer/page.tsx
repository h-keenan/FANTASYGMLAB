import type { Metadata } from "next";
import Link from "next/link";

import { AppCta, SeoPageShell } from "@/components/seo/SeoChrome";
import { PublicTradeAnalyzer } from "@/components/seo/PublicTradeAnalyzer";
import { faqLd, webApplicationLd, webPageLd } from "@/lib/seo/jsonld";
import { absoluteUrl, CHART_PATH, HUB_PATH, OG_IMAGE, TRADE_ANALYZER_PUBLIC_PATH } from "@/lib/seo/site";
import { TRADE_FAQ } from "@/lib/seo/tradeAnalyzer";

// Static shell: the value data loads client-side from /api/public-trade-values,
// so a build never depends on the value API and the page is always crawlable.

const TITLE = "Fantasy Football Trade Analyzer: Free Dynasty Trade Calculator";
const DESCRIPTION =
  "Free fantasy football trade analyzer. Search players for both sides, pick 1QB, Superflex or TE premium, and get an instant value total and fair-trade verdict.";
const PAGE_URL = absoluteUrl(TRADE_ANALYZER_PUBLIC_PATH);

export const metadata: Metadata = {
  title: TITLE,
  description: DESCRIPTION,
  // Shared links carry ?a=&b= state; they all canonicalize to the clean page.
  alternates: { canonical: PAGE_URL },
  openGraph: { title: TITLE, description: DESCRIPTION, url: PAGE_URL, type: "website", siteName: "FantasyDesk", images: [OG_IMAGE] },
  twitter: { card: "summary_large_image", title: TITLE, description: DESCRIPTION, images: [OG_IMAGE.url] },
};

const STEPS = [
  "Search for the players you would send and add them to You send.",
  "Search for the players you would get back and add them to You get.",
  "Pick 1QB or Superflex, and turn on tight end premium if your league uses it.",
  "Read the verdict: both totals, who wins on value, and how much value it would take to even it out.",
];

export default function TradeAnalyzerPublicPage() {
  return (
    <SeoPageShell
      crumbs={[
        { name: "FantasyDesk", path: "/" },
        { name: "Dynasty tools", path: HUB_PATH },
        { name: "Trade analyzer", path: TRADE_ANALYZER_PUBLIC_PATH },
      ]}
      kicker="Free tool"
      title="Fantasy Football Trade Analyzer"
      intro="Put any trade in and see who wins. Search the players on each side and get an instant value verdict for 1QB or Superflex dynasty leagues, with no account needed."
      jsonLd={[
        webPageLd({ name: TITLE, description: DESCRIPTION, path: TRADE_ANALYZER_PUBLIC_PATH }),
        webApplicationLd({ name: "FantasyDesk Trade Analyzer", description: DESCRIPTION, path: TRADE_ANALYZER_PUBLIC_PATH }),
        faqLd(TRADE_FAQ),
      ]}
    >
      <noscript>
        <p className="text-sm">The trade analyzer needs JavaScript to search players and total the values.</p>
      </noscript>
      <PublicTradeAnalyzer />

      <section className="flex flex-col gap-2" aria-labelledby="how-it-works">
        <h2 id="how-it-works" style={{ font: "var(--type-section-title)" }}>
          How to use the trade analyzer
        </h2>
        <ol className="flex list-decimal flex-col gap-1 pl-5 text-sm" style={{ color: "var(--color-text-secondary)" }}>
          {STEPS.map((step) => (
            <li key={step}>{step}</li>
          ))}
        </ol>
        <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
          Values are FantasyDesk dynasty values for a default 12-team PPR league, refreshed daily. For the full list see
          the{" "}
          <Link href={CHART_PATH} className="underline" style={{ color: "var(--color-accent)" }}>
            dynasty trade value chart
          </Link>{" "}
          or read{" "}
          <Link href="/methodology" className="underline" style={{ color: "var(--color-accent)" }}>
            how we value players
          </Link>
          .
        </p>
      </section>

      <section className="flex flex-col gap-3" aria-labelledby="faq">
        <h2 id="faq" style={{ font: "var(--type-section-title)" }}>
          Trade analyzer FAQ
        </h2>
        <dl className="flex flex-col gap-3">
          {TRADE_FAQ.map((item) => (
            <div key={item.q} className="glass-surface flex flex-col gap-1 p-4">
              <dt className="text-sm font-bold">{item.q}</dt>
              <dd className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
                {item.a}
              </dd>
            </div>
          ))}
        </dl>
      </section>

      <AppCta
        title="Know if the trade works for your team"
        body="This page can only compare values. Connect your Sleeper league and FantasyDesk checks your lineup, your needs and your trade partner, then suggests counter-offers."
      />
    </SeoPageShell>
  );
}
