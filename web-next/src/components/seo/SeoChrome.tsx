import Link from "next/link";
import type { ReactNode } from "react";

import { TrackedCtaLink } from "@/components/TrackedCtaLink";
import { ValuesCredit } from "@/components/ValuesCredit";
import {
  FANTASY_SIM_QUICKSTART_PATH,
  playoffSosInSeason,
  PLAYOFF_SOS_PATH,
  ROOKIE_RANKINGS_PATH,
  rookieContentInSeason,
  SAMPLE_LEAGUE_PATH,
  seasonMoment,
  withUtm,
} from "@/lib/seasonalLanding";
import { breadcrumbLd, serializeLd, type Crumb } from "@/lib/seo/jsonld";
import { CHART_PATH, HUB_PATH, POSITION_NAMES, RANKINGS_PATH, SEO_POSITIONS, TRADE_ANALYZER_PUBLIC_PATH } from "@/lib/seo/site";

/** Server-rendered JSON-LD script(s). */
export function JsonLd({ data }: { data: readonly unknown[] }) {
  return (
    <>
      {data.map((entry, index) => (
        <script key={index} type="application/ld+json" dangerouslySetInnerHTML={{ __html: serializeLd(entry) }} />
      ))}
    </>
  );
}

export function Breadcrumbs({ crumbs }: { crumbs: readonly Crumb[] }) {
  return (
    <nav aria-label="Breadcrumb" className="text-xs" style={{ color: "var(--color-text-muted)" }}>
      <ol className="flex flex-wrap items-center gap-1">
        {crumbs.map((crumb, index) => (
          <li key={crumb.path} className="flex items-center gap-1">
            {index > 0 ? <span aria-hidden="true">/</span> : null}
            {index === crumbs.length - 1 ? (
              <span aria-current="page">{crumb.name}</span>
            ) : (
              <Link href={crumb.path} className="underline">
                {crumb.name}
              </Link>
            )}
          </li>
        ))}
      </ol>
    </nav>
  );
}

/** Links to every spoke; rendered at the bottom of each SEO page. */
export function SpokeNav({ className = "" }: { className?: string }) {
  const moment = seasonMoment();
  const links = [
    // Season-gated pages are linked only while they are timely (and have data).
    ...(playoffSosInSeason(moment) ? [{ href: PLAYOFF_SOS_PATH, label: "Fantasy playoff strength of schedule" }] : []),
    ...(rookieContentInSeason(moment) ? [{ href: ROOKIE_RANKINGS_PATH, label: "Dynasty rookie rankings" }] : []),
    ...SEO_POSITIONS.map((p) => ({ href: RANKINGS_PATH(p), label: `Dynasty ${POSITION_NAMES[p].upper} rankings` })),
    { href: TRADE_ANALYZER_PUBLIC_PATH, label: "Fantasy football trade analyzer" },
    { href: CHART_PATH, label: "Dynasty trade value chart" },
    { href: HUB_PATH, label: "All dynasty tools" },
    { href: "/methodology", label: "How we value players" },
  ];
  return (
    <nav aria-label="More dynasty tools" className={`flex flex-col gap-2 ${className}`.trim()}>
      <h2 style={{ font: "var(--type-section-title)" }}>More dynasty tools</h2>
      <ul className="flex flex-wrap gap-2">
        {links.map((link) => (
          <li key={link.href}>
            <Link
              href={link.href}
              className="inline-flex items-center min-h-[var(--touch-target-min)] px-3 text-sm font-bold underline"
              style={{ color: "var(--color-accent)" }}
            >
              {link.label}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}

/**
 * Conversion block for every public SEO page. The primary action is the no-account sample league
 * (value before signup), then Fantasy Sim quickstart and the app itself. Links carry UTM tags
 * (utm_medium=site_cta, utm_campaign=`campaign`, utm_content=`content`) and clicks are counted as
 * `seo_cta_clicked`; site_cta tags never override a real acquisition touch (lib/attribution.ts).
 */
export function AppCta({
  title,
  body,
  campaign = "seo_page",
  content,
}: {
  title: string;
  body: string;
  campaign?: string;
  content?: string;
}) {
  const link = (href: string) => withUtm(href, "seo", campaign, content);
  return (
    <section className="glass-surface flex flex-col gap-3 p-4" aria-label="Open FantasyDesk">
      <h2 style={{ font: "var(--type-section-title)" }}>{title}</h2>
      <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
        {body}
      </p>
      <TrackedCtaLink href={link(SAMPLE_LEAGUE_PATH)} surface={campaign} destination="sample_league" variant="primary" fullWidth>
        Try a sample league
      </TrackedCtaLink>
      <div className="flex flex-col gap-2 sm:flex-row">
        <TrackedCtaLink href={link(FANTASY_SIM_QUICKSTART_PATH)} surface={campaign} destination="fantasy_sim_quickstart" variant="secondary" fullWidth>
          Play a quick Fantasy Sim game
        </TrackedCtaLink>
        <TrackedCtaLink href={link("/")} surface={campaign} destination="open_app" variant="secondary" fullWidth>
          Open FantasyDesk
        </TrackedCtaLink>
      </div>
      <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
        No account or card needed for the sample league or Fantasy Sim.
      </p>
    </section>
  );
}

/** Shared page frame: breadcrumbs, H1, intro, last-updated line, body, CTA-free footer links, credit. */
export function SeoPageShell({
  crumbs,
  kicker,
  title,
  intro,
  updated,
  jsonLd,
  children,
}: {
  crumbs: readonly Crumb[];
  kicker: string;
  title: string;
  intro: string;
  updated?: string;
  jsonLd: readonly unknown[];
  children: ReactNode;
}) {
  return (
    <main className="page-shell page-shell-prose">
      <JsonLd data={[breadcrumbLd(crumbs), ...jsonLd]} />
      <div className="flex flex-col gap-2">
        <Breadcrumbs crumbs={crumbs} />
        <p className="text-xs font-bold uppercase" style={{ color: "var(--color-accent)", letterSpacing: "0.03em" }}>
          {kicker}
        </p>
        <h1 style={{ font: "var(--font-page-title)" }}>{title}</h1>
        <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
          {intro}
        </p>
        {updated ? (
          <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
            Last updated <time dateTime={updated}>{updated}</time>
          </p>
        ) : null}
      </div>
      {children}
      <SpokeNav />
      {/* FantasyCalc Terms of Usage: visible credit linking to fantasycalc.com on every page showing
          values derived from their data, in the initial no-JS HTML. */}
      <ValuesCredit />
    </main>
  );
}
