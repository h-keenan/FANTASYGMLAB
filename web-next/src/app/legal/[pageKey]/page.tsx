import Link from "next/link";
import { notFound } from "next/navigation";

import legalContent from "@/data/legalContent.json";

/**
 * Legal/about pages (About/Disclaimer, Terms, Privacy, Subscription Terms,
 * No-Affiliation) — reuses the exact same generator-backed content mobile's
 * LegalPageScreen.tsx renders (src/data/legalContent.json, copied verbatim
 * from mobile/src/data/legalContent.json rather than re-authored, so this
 * app never drifts into a second, slightly-different copy of binding
 * legal text). No auth gate — these must be reachable by a signed-out
 * visitor, same as mobile's (LegalPage is reachable from More without a
 * league/session requirement).
 */

interface LegalSection {
  title: string;
  paragraphs: string[];
  bullets: string[];
}

interface LegalPage {
  title: string;
  kicker: string;
  note: string;
  sections: LegalSection[];
}

const CONTENT = legalContent as { lastUpdated: string; pages: Record<string, LegalPage> };

export function generateStaticParams() {
  return Object.keys(CONTENT.pages).map((pageKey) => ({ pageKey }));
}

export default async function LegalPage({ params }: { params: Promise<{ pageKey: string }> }) {
  const { pageKey } = await params;
  const page = CONTENT.pages[pageKey];
  if (!page) notFound();

  return (
    <main className="flex-1 flex flex-col gap-6 px-4 py-8 max-w-3xl w-full mx-auto">
      <div className="flex flex-col gap-2">
        <Link href="/" className="text-xs font-bold uppercase" style={{ color: "var(--color-text-muted)", letterSpacing: "0.03em" }}>
          ← FantasyDesk
        </Link>
        <p className="text-xs font-bold uppercase" style={{ color: "var(--color-accent)", letterSpacing: "0.03em" }}>
          {page.kicker}
        </p>
        <h1 style={{ font: "var(--font-page-title)" }}>{page.title}</h1>
        <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          {page.note} Last updated {CONTENT.lastUpdated}.
        </p>
      </div>

      <div className="flex flex-col gap-6">
        {page.sections.map((section) => (
          <div key={section.title} className="flex flex-col gap-2">
            <h2 style={{ font: "var(--type-section-title)" }}>{section.title}</h2>
            {section.paragraphs.map((paragraph) => (
              <p key={paragraph} className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
                {paragraph}
              </p>
            ))}
            {section.bullets.length > 0 ? (
              <ul className="flex flex-col gap-1.5 pl-5 list-disc">
                {section.bullets.map((bullet) => (
                  <li key={bullet} className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
                    {bullet}
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
        ))}
      </div>
    </main>
  );
}
