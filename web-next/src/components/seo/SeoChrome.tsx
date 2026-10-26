import Link from "next/link";
import type { ReactNode } from "react";

import { ButtonLink } from "@/components/Button";
import { ValuesCredit } from "@/components/ValuesCredit";
import { breadcrumbLd, serializeLd, type Crumb } from "@/lib/seo/jsonld";
import { CHART_PATH, HUB_PATH, POSITION_NAMES, RANKINGS_PATH, SEO_POSITIONS } from "@/lib/seo/site";

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
  const links = [
    ...SEO_POSITIONS.map((p) => ({ href: RANKINGS_PATH(p), label: `Dynasty ${POSITION_NAMES[p].upper} rankings` })),
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

export function AppCta({ title, body }: { title: string; body: string }) {
  return (
    <section className="glass-surface flex flex-col gap-3 p-4" aria-label="Open FantasyDesk">
      <h2 style={{ font: "var(--type-section-title)" }}>{title}</h2>
      <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
        {body}
      </p>
      <ButtonLink href="/" variant="primary" fullWidth>
        Open FantasyDesk
      </ButtonLink>
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
    <main className="flex-1 flex flex-col gap-6 px-4 py-8 max-w-3xl w-full mx-auto">
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
