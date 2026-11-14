"use client";

import Link from "next/link";
import type { ReactNode } from "react";

import { AccentCard } from "@/components/AccentCard";
import { StatStrip, type StatStripItem } from "@/components/StatStrip";
import { CompactModule } from "@/components/ui/CompactModule";
import { TrendChart } from "@/components/ui/TrendChart";
import { compactAriaLabel, compactParts, type CompactPart, type CompactTone } from "@/lib/compactModule";
import type { ChartInputPoint } from "@/lib/chartSeries";
import { heroParts, statStripParts, trendModel, type TrendModel } from "@/lib/moduleTemplates";

/**
 * The module template components (docs/ui-patterns.md, "Module templates"; catalog in lib/moduleTemplates.ts).
 * CompactModule is the base; these are the three shapes built on it or beside it that pages kept re-inventing:
 *   Hero             one big number/status, one context line, a trend
 *   StatStripModule  stat tiles whose collapsed form is the "Power #3 · Starters #5" summary
 *   LinkModule       a compact summary that navigates instead of expanding (a pointer to another page)
 * Mobile twin: mobile/src/components/ModuleTemplates.tsx. Tokens only, 44px targets.
 */

const TONE_COLOR: Record<CompactTone, string> = {
  success: "var(--color-success)",
  danger: "var(--color-danger)",
  warning: "var(--color-warning)",
  muted: "var(--color-text-muted)",
  accent: "var(--color-accent)",
  action: "var(--color-action)",
};

export function Hero({
  label,
  value,
  context,
  trendPoints,
  trendHigherIsBetter = true,
  trendDigits = 1,
  tone = "accent",
  badge,
  action,
  href,
  testId,
  trendName,
}: {
  /** What the number is: "Team value", "Win odds". */
  label: string;
  /** The one big number or status: "71", "#3", "Contender". */
  value: string;
  /** One line of context: "Top 3rd of 12 teams". */
  context?: string | null;
  /** Recent values, oldest first. Two or more render a sparkline and a signed delta; fewer render no trend at all. */
  trendPoints?: ReadonlyArray<number | null | undefined>;
  /** False for ranks (a falling number is good). */
  trendHigherIsBetter?: boolean;
  trendDigits?: number;
  tone?: CompactTone;
  /** A small pill beside the label (archetype, status). */
  badge?: ReactNode;
  action?: ReactNode;
  /** Makes the whole hero a link. */
  href?: string;
  testId?: string;
  trendName?: string;
}) {
  const trend: TrendModel | null = trendPoints ? trendModel(trendPoints, trendHigherIsBetter, trendDigits) : null;
  const chartPoints: ChartInputPoint[] | null =
    trendPoints && trend ? trendPoints.map((y, i) => ({ x: i, y: typeof y === "number" ? y : null })) : null;
  const name = compactAriaLabel(label, heroParts({ label, value, context, trend }), false).replace(/\. (Expand|Collapse)$/, "");
  const body = (
    <>
      <div className="flex items-center gap-2">
        <span className="text-[0.6875rem] font-extrabold uppercase" style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}>
          {label}
        </span>
        {badge}
      </div>
      <div className="flex items-end gap-3">
        <span style={{ font: "var(--type-primary-metric)", color: "var(--color-text-primary)" }} data-testid="hero-value">
          {value}
        </span>
        {trend ? (
          <span className="pb-1 text-sm font-extrabold" style={{ color: TONE_COLOR[trend.tone] }} data-testid="hero-trend">
            {trend.direction === "up" ? "▲" : trend.direction === "down" ? "▼" : "–"} {trend.label}
          </span>
        ) : null}
        {chartPoints ? (
          <div className="ml-auto h-10 w-24 shrink-0" aria-hidden="true">
            <TrendChart points={chartPoints} name={trendName ?? label} variant="compact" height={40} />
          </div>
        ) : null}
      </div>
      {context ? (
        <p className="text-sm" style={{ color: "var(--color-text-secondary)" }} data-testid="hero-context">
          {context}
        </p>
      ) : null}
    </>
  );
  return (
    <AccentCard accent={TONE_COLOR[tone]} as="section" data-testid={testId ?? "hero"}>
      {href ? (
        <Link href={href} aria-label={name} className="flex flex-col gap-1" style={{ color: "inherit", textDecoration: "none", minHeight: "var(--touch-target-min)" }}>
          {body}
        </Link>
      ) : (
        <div className="flex flex-col gap-1" role="group" aria-label={name}>
          {body}
        </div>
      )}
      {action ? <div className="flex">{action}</div> : null}
    </AccentCard>
  );
}

/** Stat tiles as a module: collapsed shows "Power #3 · Starters #5 · Age 26.1", expanded the full tiles. */
export function StatStripModule({
  id,
  title,
  items,
  league,
  columns = 3,
  defaultOpen = false,
  tone = "accent",
  action,
  extraParts,
  footer,
  testId,
}: {
  id: string;
  title: string;
  items: StatStripItem[];
  league?: { id: string; name: string };
  columns?: 3 | 4;
  defaultOpen?: boolean;
  tone?: CompactTone;
  action?: ReactNode;
  /** Parts appended after the stat summary (e.g. an "Injured: 2" warning). */
  extraParts?: ReadonlyArray<CompactPart | null | undefined | false | "">;
  /** Shown under the tiles when expanded (glossary, beginner help). */
  footer?: ReactNode;
  testId?: string;
}) {
  const parts = compactParts([...statStripParts(items.map((i) => ({ label: shortLabel(i.label), value: i.value, tone: i.tone === "risk" ? "danger" : i.tone === "positive" ? "success" : undefined }))), ...(extraParts ?? [])]);
  const rows: StatStripItem[][] = [];
  for (let i = 0; i < items.length; i += columns) rows.push(items.slice(i, i + columns));
  return (
    <CompactModule id={id} title={title} parts={parts} tone={tone} defaultOpen={defaultOpen} action={action} testId={testId}>
      {rows.map((row, i) => (
        <StatStrip key={i} items={row} columns={columns} league={league} />
      ))}
      {footer}
    </CompactModule>
  );
}

/** "Power Rank" -> "Power", "Starter Strength" -> "Starters", "Avg Age" -> "Age": the summary line uses the short noun. */
export function shortLabel(label: string): string {
  const map: Record<string, string> = {
    "Power Rank": "Power",
    "Franchise Rank": "Franchise",
    "Starter Strength": "Starters",
    "Bench Strength": "Bench",
    "Avg Age": "Age",
    "Average Age": "Age",
    "Injured starters": "Injured",
  };
  return map[label] ?? label;
}

/** A compact summary that goes to another page (a pointer, not an expander). Same look as CompactModule, chevron is an arrow. */
export function LinkModule({
  title,
  parts,
  href,
  tone = "accent",
  testId,
}: {
  title: string;
  parts: ReadonlyArray<CompactPart | null | undefined | false | "">;
  href: string;
  tone?: CompactTone;
  testId?: string;
}) {
  const shown = compactParts(parts);
  return (
    <AccentCard accent={TONE_COLOR[tone]} as="section" compact data-testid={testId}>
      <Link
        href={href}
        aria-label={`${title}: ${shown.map((p) => p.text).join(" · ")}. Open`}
        className="flex items-center gap-2"
        style={{ minHeight: "var(--touch-target-min)", color: "inherit", textDecoration: "none" }}
      >
        <span className="flex min-w-0 flex-1 flex-col">
          <span className="text-[0.6875rem] font-extrabold uppercase" style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}>
            {title}
          </span>
          <span className="text-sm leading-snug" data-testid="compact-summary" style={{ display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden" }}>
            {shown.map((part, i) => (
              <span key={part.key}>
                {i > 0 ? <span style={{ color: "var(--color-text-muted)" }}>{" · "}</span> : null}
                <span style={{ color: part.tone ? TONE_COLOR[part.tone] : "var(--color-text-primary)", fontWeight: part.strong ? 800 : 600 }}>{part.text}</span>
              </span>
            ))}
          </span>
        </span>
        <span aria-hidden="true" style={{ color: "var(--color-accent)" }}>
          →
        </span>
      </Link>
    </AccentCard>
  );
}
