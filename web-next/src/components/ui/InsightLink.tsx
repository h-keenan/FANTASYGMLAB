"use client";

import Link from "next/link";
import type { CSSProperties, ReactNode } from "react";

import { insightHref } from "@/lib/insightHref";
import { insightAriaLabel, type InsightKey } from "@/lib/insightLinks";

import "./ui.css";

export type InsightLinkProps = {
  /** Which fact this is; lib/insightLinks.ts says where it goes. */
  insight: InsightKey;
  league: { id: string; name: string };
  /** What a screen reader hears before the destination: ["Avg Age", "26.1", "League avg 25.2"]. */
  spoken: ReadonlyArray<string | null | undefined>;
  children: ReactNode;
  className?: string;
  style?: CSSProperties;
  testId?: string;
};

/**
 * The tappable-card wrapper for any stat, insight card or chip that states a
 * fact about the user's league or team: a real link to the page that explains
 * it, with the shared pressed/focus state. NO chevron: the whole tile is the
 * affordance (lib/rowAffordance.ts). Keeps the child's own glass look.
 * Add the fact to INSIGHT_TARGETS first; this never takes a raw href.
 */
export function InsightLink({ insight, league, spoken, children, className = "", style, testId }: InsightLinkProps) {
  return (
    <Link
      href={insightHref(insight, league)}
      className={`ui-insight ${className}`.trim()}
      style={style}
      aria-label={insightAriaLabel(insight, spoken)}
      data-insight={insight}
      data-testid={testId}
    >
      {children}
    </Link>
  );
}
