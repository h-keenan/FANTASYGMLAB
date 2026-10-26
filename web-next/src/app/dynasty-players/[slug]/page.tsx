import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { AppCta, SeoPageShell } from "@/components/seo/SeoChrome";
import { isPlayerPageIndexable, neighbors, playerDescription, playerFacts } from "@/lib/seo/content";
import { webPageLd } from "@/lib/seo/jsonld";
import { fetchBoard, formatUpdated, PLAYER_PAGE_LIMIT } from "@/lib/seo/publicValues";
import {
  absoluteUrl,
  parsePosition,
  PLAYER_PATH,
  POSITION_NAMES,
  RANKINGS_PATH,
  OG_IMAGE,
} from "@/lib/seo/site";
import { assignSlugs, findPlayerBySlug } from "@/lib/seo/slug";

// Top ~300 players by dynasty value. Generated on first request, cached daily
// (ISR); an unknown slug, a player outside the top 300, or a player without
// enough real data is a 404, never a placeholder page.
export const revalidate = 86400; // daily ISR (segment config must be a literal)
export const dynamicParams = true;
export function generateStaticParams() {
  return [];
}

async function load(slug: string) {
  const [oneQb, superflex] = await Promise.all([fetchBoard("1qb"), fetchBoard("superflex")]);
  const eligible = oneQb.players.filter((p) => p.overall_rank <= PLAYER_PAGE_LIMIT);
  const player = findPlayerBySlug(eligible, slug);
  if (!player) return null;
  const sf = superflex.players.find((p) => p.player_id === player.player_id) ?? null;
  if (!isPlayerPageIndexable(player, oneQb, sf)) return null;
  return { oneQb, player, sf, slugs: assignSlugs(eligible) };
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params;
  const data = await load(slug);
  if (!data) return { robots: { index: false, follow: false } };
  const { player } = data;
  const pos = POSITION_NAMES[parsePosition(player.position) ?? "qb"].upper;
  const title = `${player.name} Dynasty Value: ${pos}${player.position_rank}, #${player.overall_rank} Overall`;
  const description = playerDescription(player);
  const url = absoluteUrl(PLAYER_PATH(slug));
  return {
    title,
    description,
    alternates: { canonical: url },
    openGraph: { title, description, url, type: "article", siteName: "FantasyDesk", images: [OG_IMAGE] },
    twitter: { card: "summary_large_image", title, description, images: [OG_IMAGE.url] },
  };
}

export default async function DynastyPlayerPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const data = await load(slug);
  if (!data) notFound();
  const { oneQb, player, sf, slugs } = data;
  const key = parsePosition(player.position)!;
  const names = POSITION_NAMES[key];
  const facts = playerFacts(player, oneQb, sf);
  const { above, below } = neighbors(player, oneQb);
  const title = `${player.name} Dynasty Value: ${names.upper}${player.position_rank}, #${player.overall_rank} Overall`;
  const path = PLAYER_PATH(slug);

  const peerLink = (label: string, peer: typeof above) => {
    if (!peer) return null;
    const peerSlug = peer.overall_rank <= PLAYER_PAGE_LIMIT ? slugs.get(peer.player_id) : null;
    return (
      <li key={label}>
        {label}:{" "}
        {peerSlug ? (
          <Link href={PLAYER_PATH(peerSlug)} className="underline font-bold">
            {peer.name}
          </Link>
        ) : (
          <span className="font-bold">{peer.name}</span>
        )}{" "}
        ({peer.score.toLocaleString("en-US")})
      </li>
    );
  };

  return (
    <SeoPageShell
      crumbs={[
        { name: "FantasyDesk", path: "/" },
        { name: "Dynasty tools", path: "/dynasty-tools" },
        { name: `${names.upper} rankings`, path: RANKINGS_PATH(key) },
        { name: player.name, path },
      ]}
      kicker={`${names.upper}${player.team ? ` · ${player.team}` : ""}`}
      title={title}
      intro={facts[0]}
      updated={formatUpdated(oneQb.source_updated_at)}
      jsonLd={[webPageLd({ name: title, description: playerDescription(player), path, dateModified: oneQb.source_updated_at })]}
    >
      <section className="glass-surface grid grid-cols-2 gap-3 p-4" aria-label="Dynasty value summary">
        <Stat label="Dynasty value" value={player.score.toLocaleString("en-US")} />
        <Stat label={`${names.upper} rank`} value={`#${player.position_rank}`} />
        <Stat label="Overall rank" value={`#${player.overall_rank}`} />
        {sf ? <Stat label="Superflex value" value={sf.score.toLocaleString("en-US")} /> : null}
        {player.age !== null ? <Stat label="Age" value={String(player.age)} /> : null}
      </section>

      <section className="flex flex-col gap-2">
        <h2 style={{ font: "var(--type-section-title)" }}>Dynasty outlook</h2>
        {facts.slice(1).map((fact) => (
          <p key={fact} className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
            {fact}
          </p>
        ))}
        <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          Values are for a default 12-team PPR dynasty league. Your league&apos;s scoring and roster change them.
        </p>
      </section>

      {above || below ? (
        <section className="flex flex-col gap-2">
          <h2 style={{ font: "var(--type-section-title)" }}>Nearby {names.plural}</h2>
          <ul className="flex flex-col gap-1 text-sm">
            {peerLink("Ranked just above", above)}
            {peerLink("Ranked just below", below)}
          </ul>
          <Link href={RANKINGS_PATH(key)} className="text-sm font-bold underline" style={{ color: "var(--color-accent)" }}>
            See all dynasty {names.upper} rankings
          </Link>
        </section>
      ) : null}

      <AppCta
        title={`What is ${player.name} worth to your team?`}
        body="FantasyDesk values him for your league's settings and your roster, then tells you whether a trade offer or waiver move makes sense."
      />
    </SeoPageShell>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col">
      <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
        {label}
      </span>
      <span className="text-xl font-bold">{value}</span>
    </div>
  );
}
