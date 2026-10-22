import Link from "next/link";

import { ValuesCredit } from "@/components/ValuesCredit";
import methodologyContent from "@/data/methodologyContent.json";

/**
 * "How We Evaluate" — reuses the exact same generator-backed content
 * mobile's HowWeEvaluateScreen.tsx renders (src/data/methodologyContent.json,
 * copied verbatim from mobile/src/data/methodologyContent.json rather than
 * re-authored, same convention as legal/[pageKey]/page.tsx). No auth gate —
 * public, non-league-scoped prose (modules.methodology_page.PAGE_KEY ==
 * "methodology"), same as mobile's (reachable from More without a
 * league/session requirement).
 *
 * coridian_, 2026-10-19: this page didn't exist anywhere in web-next (not
 * even a Streamlit redirect) — the one genuine content gap found while
 * auditing "menu pages missing from the site vs the app".
 */

interface MethodologySection {
  title: string;
  paragraphs: string[];
  bullets: string[];
}

interface MethodologyContent {
  title: string;
  kicker: string;
  note: string;
  sections: MethodologySection[];
}

const CONTENT = methodologyContent as MethodologyContent;

export default function MethodologyPage() {
  return (
    <main className="flex-1 flex flex-col gap-6 px-4 py-8 max-w-3xl w-full mx-auto">
      <div className="flex flex-col gap-2">
        <Link href="/" className="text-xs font-bold uppercase" style={{ color: "var(--color-text-muted)", letterSpacing: "0.03em" }}>
          ← FantasyDesk
        </Link>
        <p className="text-xs font-bold uppercase" style={{ color: "var(--color-accent)", letterSpacing: "0.03em" }}>
          {CONTENT.kicker}
        </p>
        <h1 style={{ font: "var(--font-page-title)" }}>{CONTENT.title}</h1>
        <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>{CONTENT.note}</p>
      </div>

      <div className="flex flex-col gap-6">
        {CONTENT.sections.map((section) => (
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

      {/* FantasyCalc's Terms of Usage require at least one attribution link
          that's public (no login or paywall) and in the initial HTML without
          JavaScript. This page is a server-rendered, unauthenticated route,
          so this credit is that link. See ValuesCredit.tsx. */}
      <ValuesCredit />
    </main>
  );
}
