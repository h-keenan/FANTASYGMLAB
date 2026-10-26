import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { AppCta, SeoPageShell } from "@/components/seo/SeoChrome";
import { ValueTable, type ValueRow } from "@/components/seo/ValueTable";
import { isPageEligible, isRankingsIndexable, RANKINGS_ROWS } from "@/lib/seo/content";
import { itemListLd, webPageLd } from "@/lib/seo/jsonld";
import { fetchBoard, formatUpdated, playersAt } from "@/lib/seo/publicValues";
import {
  absoluteUrl,
  parsePosition,
  PLAYER_PATH,
  POSITION_NAMES,
  RANKINGS_PATH,
  type SeoPosition,
  OG_IMAGE,
} from "@/lib/seo/site";
import { assignSlugs } from "@/lib/seo/slug";

// Daily ISR. No build-time params: pages are generated on first request
// (the value API is not guaranteed reachable at build time) and then cached.
export const revalidate = 86400; // daily ISR (segment config must be a literal)
export const dynamicParams = true;
export function generateStaticParams() {
  return [];
}

async function load(position: SeoPosition) {
  const [oneQb, superflex] = await Promise.all([fetchBoard("1qb"), position === "qb" ? fetchBoard("superflex") : null]);
  const names = POSITION_NAMES[position];
  const players = playersAt(oneQb, names.upper).slice(0, RANKINGS_ROWS);
  return { oneQb, superflex, players, names };
}

function copy(position: SeoPosition, year: number) {
  const names = POSITION_NAMES[position];
  return {
    title: `Dynasty ${names.upper} Rankings ${year}: Top ${RANKINGS_ROWS} ${names.plural} by Value`,
    description: `Dynasty ${names.upper} rankings with value, age and workload trend for the top ${RANKINGS_ROWS} ${names.plural}, updated daily from FantasyDesk's player valuations.`,
  };
}

export async function generateMetadata({ params }: { params: Promise<{ position: string }> }): Promise<Metadata> {
  const key = parsePosition((await params).position);
  if (!key) return { robots: { index: false, follow: false } };
  const { oneQb, players } = await load(key);
  const { title, description } = copy(key, new Date(oneQb.source_updated_at).getUTCFullYear());
  const url = absoluteUrl(RANKINGS_PATH(key));
  if (!isRankingsIndexable(players)) return { robots: { index: false, follow: false } };
  return {
    title,
    description,
    alternates: { canonical: url },
    openGraph: { title, description, url, type: "website", siteName: "FantasyDesk", images: [OG_IMAGE] },
    twitter: { card: "summary_large_image", title, description, images: [OG_IMAGE.url] },
  };
}

export default async function DynastyRankingsPage({ params }: { params: Promise<{ position: string }> }) {
  const key = parsePosition((await params).position);
  if (!key) notFound();
  const { oneQb, superflex, players, names } = await load(key);
  if (!isRankingsIndexable(players)) notFound();

  const slugs = assignSlugs(oneQb.players.filter(isPageEligible));
  const sfById = new Map((superflex?.players ?? []).map((p) => [p.player_id, p]));
  const rows: ValueRow[] = players.map((player) => {
    const sf = sfById.get(player.player_id);
    return {
      rank: player.position_rank,
      player,
      slug: isPageEligible(player) ? (slugs.get(player.player_id) ?? null) : null,
      extra: sf ? { value: sf.score, rank: sf.position_rank } : null,
    };
  });

  const updated = formatUpdated(oneQb.source_updated_at);
  const { title, description } = copy(key, new Date(oneQb.source_updated_at).getUTCFullYear());
  const path = RANKINGS_PATH(key);
  const intro =
    key === "qb"
      ? `The top ${players.length} dynasty quarterbacks ranked by FantasyDesk value in a 12-team PPR 1QB league, with the Superflex value alongside because quarterbacks gain the most when a second QB can start.`
      : `The top ${players.length} dynasty ${names.plural} ranked by FantasyDesk value in a 12-team PPR 1QB league. Age and the model's workload trend signal are shown under each name.`;

  return (
    <SeoPageShell
      crumbs={[
        { name: "FantasyDesk", path: "/" },
        { name: "Dynasty tools", path: "/dynasty-tools" },
        { name: `${names.upper} rankings`, path },
      ]}
      kicker="Dynasty rankings"
      title={title}
      intro={intro}
      updated={updated}
      jsonLd={[
        webPageLd({ name: title, description, path, dateModified: oneQb.source_updated_at }),
        itemListLd({
          name: title,
          path,
          items: rows.map((r) => ({ name: r.player.name, path: r.slug ? PLAYER_PATH(r.slug) : undefined })),
        }),
      ]}
    >
      <ValueTable
        rows={rows}
        valueHeader="Value"
        extraHeader={key === "qb" ? "Superflex" : undefined}
        caption={`Dynasty ${names.upper} rankings`}
      />
      <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
        Value is FantasyDesk&apos;s dynasty score on a scale that tops out around 10,000, for a 12-team PPR league. See{" "}
        <Link href="/methodology" className="underline">
          how we value players
        </Link>
        .
      </p>
      <AppCta
        title="Rankings for your league, not a generic one"
        body={`These are default-settings values. FantasyDesk re-values every ${names.singular} for your league's scoring and roster, then tells you which trades and waiver moves to make.`}
      />
    </SeoPageShell>
  );
}
