"use client";

import Link from "next/link";
import { useId, useState, type ReactNode } from "react";

import { AccentCard } from "@/components/AccentCard";
import { FillBar } from "@/components/SnapshotTile";
import type { StatStripItem } from "@/components/StatStrip";
import { InsightLink } from "@/components/ui/InsightLink";
import { TrendChart } from "@/components/ui/TrendChart";
import { compactAriaLabel, compactParts, compactSummaryText, type CompactPart, type CompactTone } from "@/lib/compactModule";
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

/**
 * THE stat strip (docs/ui-patterns.md, "Stat strip"). COMPACT (V1): the stats as one row of small glass tiles, each
 * with its value and a caption, always visible, each a link to the page that explains it (InsightLink destinations).
 * EXPANDED (V2): one tap on "Rank bars" turns the same stats into labelled standing bars (rank position or win share
 * as a bar, with the value). Items with no honest relative scale (average age) list their value without a bar.
 * Shared by FantasyDesk (My Team, Today) and the Fantasy Sim franchise page; mobile twin is `StatStripModule`.
 */
export function StatStripModule({
  id,
  title,
  items,
  league,
  columns = 3,
  defaultOpen = false,
  tone = "accent",
  action,
  footer,
  testId,
}: {
  id: string;
  title: string;
  items: StatStripItem[];
  league?: { id: string; name: string };
  columns?: 3 | 4;
  /** Starts with the rank bars open. */
  defaultOpen?: boolean;
  tone?: CompactTone;
  action?: ReactNode;
  /** Shown under the bars when expanded (glossary, beginner help). */
  footer?: ReactNode;
  testId?: string;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const bodyId = useId();
  const hasBars = items.some((item) => item.fill != null);
  const expandable = true;
  const summary = compactSummaryText(statStripParts(items.map((i) => ({ label: shortLabel(i.label), value: i.value }))));
  const cols = Math.min(items.length, columns) || 1;
  return (
    <AccentCard accent={TONE_COLOR[tone]} as="section" compact data-testid={testId ?? `stat-strip-${id}`}>
      <div className="flex items-center justify-between gap-2">
        <h3 className="m-0 text-[0.6875rem] font-extrabold uppercase" style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}>
          {title}
        </h3>
        {action}
      </div>
      <div className="grid gap-2" style={{ gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))` }} role="group" aria-label={`${title}: ${summary}`} data-testid="stat-strip-tiles">
        {items.map(({ insight, ...item }) => {
          const tile = <StatStripTile key={item.label} item={item} />;
          if (!insight || !league) return tile;
          return (
            <InsightLink key={item.label} insight={insight} league={league} spoken={[item.label, item.value, item.note]} noChevron>
              {tile}
            </InsightLink>
          );
        })}
      </div>
      {expandable ? (
        <button
          type="button"
          className="tap-link flex items-center justify-center gap-1 self-stretch text-xs font-bold"
          style={{ minHeight: "var(--touch-target-min)", color: "var(--color-accent)" }}
          aria-expanded={open}
          aria-controls={bodyId}
          onClick={() => setOpen(!open)}
          data-testid="stat-strip-toggle"
        >
          {hasBars ? (open ? "Hide rank bars" : "Rank bars") : open ? "Hide details" : "Details"}
          <span aria-hidden="true">{open ? "▴" : "▾"}</span>
        </button>
      ) : null}
      {open ? (
        <div id={bodyId} className="flex flex-col gap-2" data-testid="stat-strip-bars">
          {
            <ul className="m-0 flex list-none flex-col gap-1 p-0">
              {items.map(({ insight, ...item }) => {
                const row = (
                  <span className="grid min-h-[var(--touch-target-min)] grid-cols-[6.5rem_minmax(0,1fr)_3.5rem] items-center gap-2 text-sm">
                    <span style={{ color: "var(--color-text-secondary)" }}>{item.label}</span>
                    {item.fill != null ? <FillBar fill={item.fill} label={item.label} /> : <span aria-hidden="true" />}
                    <span className="text-right font-extrabold tabular-nums">{item.value}</span>
                  </span>
                );
                return (
                  <li key={item.label}>
                    {insight && league ? (
                      <InsightLink insight={insight} league={league} spoken={[item.label, item.value, item.note]} noChevron>
                        {row}
                      </InsightLink>
                    ) : (
                      row
                    )}
                  </li>
                );
              })}
            </ul>
          }
          {footer}
        </div>
      ) : null}
    </AccentCard>
  );
}

function StatStripTile({ item }: { item: Omit<StatStripItem, "insight"> }) {
  const color = item.tone === "risk" ? "var(--color-danger)" : item.tone === "positive" ? "var(--color-success)" : item.tone === "premium" ? "var(--color-premium)" : "var(--color-text-primary)";
  return (
    <span className="glass-surface flex min-w-0 flex-col items-center gap-0.5 px-1.5 py-2 text-center" style={{ borderColor: item.tone === "premium" ? "var(--color-premium)" : undefined }} data-testid="stat-strip-tile">
      <span className="max-w-full truncate text-[0.6875rem] font-extrabold uppercase" style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}>
        {shortLabel(item.label)}
      </span>
      <span className="max-w-full truncate text-lg font-extrabold tabular-nums leading-tight" style={{ color }}>
        {item.value}
      </span>
      {item.note ? (
        <span className="text-[0.6875rem] leading-tight" style={{ color: "var(--color-text-muted)" }}>
          {item.note}
        </span>
      ) : null}
    </span>
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
                <span style={{ color: part.tone ? TONE_COLOR[part.tone] : "var(--color-text-primary)", fontWeight: part.strong ? 800 : 600, whiteSpace: part.text.length <= 14 ? "nowrap" : undefined }}>{part.text}</span>
              </span>
            ))}
          </span>
        </span>
        <span aria-hidden="true" data-row-arrow style={{ color: "var(--color-accent)" }}>
          →
        </span>
      </Link>
    </AccentCard>
  );
}
