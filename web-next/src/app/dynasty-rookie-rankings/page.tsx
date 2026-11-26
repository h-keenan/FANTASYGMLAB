import type { Metadata } from "next";
import Link from "next/link";

import { AppCta, SeoPageShell } from "@/components/seo/SeoChrome";
import { ValueTable, type ValueRow } from "@/components/seo/ValueTable";
import { isPageEligible } from "@/lib/seo/content";
import { itemListLd, webPageLd } from "@/lib/seo/jsonld";
import { fetchBoard, formatUpdated } from "@/lib/seo/publicValues";
import { absoluteUrl, OG_IMAGE, PLAYER_PATH } from "@/lib/seo/site";
import { assignSlugs } from "@/lib/seo/slug";
import { MIN_ROOKIES, rookieRows } from "@/lib/seo/rookies";
import { ROOKIE_RANKINGS_PATH, rookieContentInSeason, seasonMoment } from "@/lib/seasonalLanding";

// Season-gated: only after the NFL draft through the start of the season, and only when the public value board
// actually contains a rookie class. Otherwise the page renders a noindex notice instead of an empty ranking.
// Rendered per request (the value fetches are cached for a day by fetch itself): the build cannot reach the API,
// and the season gate must follow the clock rather than freeze at build time.
export const dynamic = "force-dynamic";

async function load() {
  const moment = seasonMoment();
  if (!rookieContentInSeason(moment)) return { moment, oneQb: null, rookies: [], live: false as const };
  try {
    const [oneQb, superflex] = await Promise.all([fetchBoard("1qb"), fetchBoard("superflex")]);
    const rookies = rookieRows(oneQb, superflex);
    return { moment, oneQb, rookies, live: rookies.length >= MIN_ROOKIES };
  } catch {
    return { moment, oneQb: null, rookies: [], live: false as const };
  }
}

export async function generateMetadata(): Promise<Metadata> {
  const { moment, live } = await load();
  const year = moment.season + 1;
  const title = `Dynasty Rookie Rankings ${year}: Top Rookies by Dynasty Value`;
  const description = "The incoming rookie class ranked by dynasty value in 1QB and Superflex leagues, with position, team and age. Updated daily.";
  const url = absoluteUrl(ROOKIE_RANKINGS_PATH);
  return {
    title,
    description,
    alternates: { canonical: url },
    robots: live ? undefined : { index: false, follow: true },
    openGraph: { title, description, url, type: "website", siteName: "FantasyDesk", images: [OG_IMAGE] },
    twitter: { card: "summary_large_image", title, description, images: [OG_IMAGE.url] },
  };
}

export default async function DynastyRookieRankingsPage() {
  const { moment, oneQb, rookies, live } = await load();
  const year = moment.season + 1;
  const title = `Dynasty Rookie Rankings ${year}`;
  const crumbs = [
    { name: "FantasyDesk", path: "/" },
    { name: "Dynasty tools", path: "/dynasty-tools" },
    { name: "Rookie rankings", path: ROOKIE_RANKINGS_PATH },
  ];

  if (!live || !oneQb) {
    return (
      <SeoPageShell
        crumbs={crumbs}
        kicker="Dynasty rookies"
        title={title}
        intro="Rookie rankings open after the NFL draft, once the class has teams and values."
        jsonLd={[]}
      >
        <section className="glass-surface p-4 flex flex-col gap-2">
          <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
            Nothing to rank yet. In the meantime, see the current dynasty rankings.
          </p>
          <Link href="/dynasty-rankings/qb" className="text-sm font-bold underline" style={{ color: "var(--color-accent)" }}>
            Dynasty QB rankings
          </Link>
        </section>
        <AppCta title="Scout the class in the app" body="College scouting and Draft Center help you plan your rookie draft." campaign="rookie_rankings_page" />
      </SeoPageShell>
    );
  }

  const slugs = assignSlugs(oneQb.players.filter(isPageEligible));
  const rows: ValueRow[] = rookies.map((r, i) => ({
    rank: i + 1,
    player: r.player,
    slug: isPageEligible(r.player) ? (slugs.get(r.player.player_id) ?? null) : null,
    extra: r.superflex ? { value: r.superflex.score, rank: r.superflex.overall_rank } : null,
  }));
  const description = "The incoming rookie class ranked by dynasty value in 1QB and Superflex leagues.";

  return (
    <SeoPageShell
      crumbs={crumbs}
      kicker="Dynasty rookies"
      title={title}
      intro={`The ${rows.length} highest-valued first-year players on our public dynasty board, ranked by value in a 12-team PPR 1QB league, with the Superflex value alongside.`}
      updated={formatUpdated(oneQb.source_updated_at)}
      jsonLd={[
        webPageLd({ name: title, description, path: ROOKIE_RANKINGS_PATH, dateModified: oneQb.source_updated_at }),
        itemListLd({ name: title, path: ROOKIE_RANKINGS_PATH, items: rows.map((r) => ({ name: r.player.name, path: r.slug ? PLAYER_PATH(r.slug) : undefined })) }),
      ]}
    >
      <ValueTable rows={rows} valueHeader="Value" extraHeader="Superflex" caption="Dynasty rookie rankings" />
      <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
        A rookie here is a player with no prior NFL seasons on the value board. Values are default 12-team PPR settings and move with landing spot and
        depth chart news.{" "}
        <Link href="/methodology" className="underline">
          How we value players
        </Link>
        .
      </p>
      <AppCta
        title="Rank rookies for your league"
        body="FantasyDesk values the class for your league's settings and your roster needs, then tells you who to take with your pick."
        campaign="rookie_rankings_page"
      />
    </SeoPageShell>
  );
}
