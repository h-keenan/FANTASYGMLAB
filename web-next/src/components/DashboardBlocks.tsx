import Link from "next/link";
import type { ReactNode } from "react";

import type { BriefingItem, DashboardResponse } from "@/lib/api";
import { AccentCard } from "@/components/AccentCard";
import { ToneBadge } from "@/components/ToneBadge";
import { BeginnerHelp } from "@/components/BeginnerHelp";
import { SectionHeading } from "@/components/SectionHeading";
import {
  buildNowChips,
  tradeIdeasLine,
  tradesGoalLine,
  TRADES_BLOCK_COPY,
  type DashboardAttentionEntry,
  type DashboardNowChip,
} from "@/lib/dashboardLayout";
import { GAME_PLAN_INTERNAL_ROUTES, gamePlanTileHref, resolveGamePlanTargetPlayerId } from "@/lib/gamePlanPresentation";
import { thisWeekHref } from "@/lib/thisWeek";

const TONE_COLOR: Record<DashboardNowChip["tone"], string> = {
  positive: "var(--color-success)",
  risk: "var(--color-danger)",
  waiver: "var(--color-accent)",
  neutral: "var(--color-text-primary)",
};

function chipHref(chip: DashboardNowChip, leagueId: string, leagueName: string): string {
  if (chip.route === "alerts") return `/alerts/${encodeURIComponent(leagueId)}?name=${encodeURIComponent(leagueName)}`;
  return thisWeekHref(chip.route, leagueId, leagueName);
}

/**
 * "At a glance": a compact row of real status chips (lineup, trade
 * deadline, alerts, waivers). Each is one tap to the place that fixes it.
 * Renders nothing when there is no real status to show.
 */
export function DashboardNowStrip({
  data,
  leagueId,
  leagueName,
  exclude,
}: {
  data: DashboardResponse;
  leagueId: string;
  leagueName: string;
  /** Chip keys already listed under "Needs attention". */
  exclude?: readonly string[];
}) {
  const alertCount = data.items.filter((item) => item.category !== "top_priority").length;
  const chips = buildNowChips(data.this_week?.rows, data.trade_window, alertCount, exclude);
  if (chips.length === 0) return null;
  return (
    <section aria-label="At a glance" data-testid="dashboard-now-strip" className="grid grid-cols-2 gap-2 [&>*:last-child:nth-child(odd)]:col-span-2">
      {chips.map((chip) => (
        <Link
          key={chip.key}
          href={chipHref(chip, leagueId, leagueName)}
          className="glass-surface flex flex-col px-3 py-2"
          style={{ minHeight: "var(--touch-target-min)", color: "inherit", textDecoration: "none" }}
        >
          <span className="text-xs uppercase font-bold" style={{ color: "var(--color-text-muted)", letterSpacing: "0.04em" }}>
            {chip.label}
          </span>
          <span className="text-sm font-bold" style={{ color: TONE_COLOR[chip.tone] }}>
            {chip.value}
          </span>
        </Link>
      ))}
    </section>
  );
}

/**
 * "Needs attention": a compact list of the few urgent items, each one line with
 * one link to where it is handled. Urgency is read only from existing fields
 * (lib/dashboardLayout.ts buildNeedsAttention); the full plan stays on GM Plan.
 * Renders nothing when nothing is urgent.
 */
export function DashboardNeedsAttention({
  entries,
  leagueId,
  leagueName,
}: {
  entries: DashboardAttentionEntry<BriefingItem>[];
  leagueId: string;
  leagueName: string;
}) {
  if (entries.length === 0) return null;
  const id = encodeURIComponent(leagueId);
  const query = `?name=${encodeURIComponent(leagueName)}`;
  const hrefFor = (entry: DashboardAttentionEntry<BriefingItem>): string => {
    if (entry.target === "matchup") return thisWeekHref("matchup", leagueId, leagueName);
    if (entry.target === "gm_plan" || !entry.item) return `/gm-plan/${id}${query}`;
    const route = GAME_PLAN_INTERNAL_ROUTES[entry.item.destination] ?? "gm-plan";
    return gamePlanTileHref(route, leagueId, leagueName, resolveGamePlanTargetPlayerId(entry.item));
  };
  return (
    <section className="flex flex-col gap-2" aria-labelledby="needs-attention-heading" data-testid="dashboard-needs-attention">
      <SectionHeading id="needs-attention-heading">
        Needs attention
      </SectionHeading>
      <AccentCard accent="var(--color-danger)" compact>
        <ul className="flex flex-col" style={{ listStyle: "none", margin: 0, padding: 0 }}>
          {entries.map((entry, index) => (
            <li key={`${entry.source}-${index}`} style={index > 0 ? { borderTop: "1px solid var(--color-border)" } : undefined}>
              <Link
                href={hrefFor(entry)}
                className="flex items-center gap-2 py-2.5"
                style={{ minHeight: 44, color: "inherit", textDecoration: "none" }}
              >
                <ToneBadge label={entry.badge} color="var(--color-danger)" />
                <span className="min-w-0 flex-1 flex flex-col">
                  <span className="text-sm font-bold truncate">{entry.headline}</span>
                  <span className="text-xs truncate" style={{ color: "var(--color-text-secondary)" }}>
                    {entry.why}
                  </span>
                </span>
                <span aria-hidden="true" style={{ color: "var(--color-accent)" }}>
                  →
                </span>
              </Link>
            </li>
          ))}
        </ul>
      </AccentCard>
    </section>
  );
}

/**
 * Trade ideas on the Dashboard are one line: a count and a link. The idea
 * cards live only on GM Plan and Trade Hub.
 */
export function DashboardTradesBlock({
  data,
  tradeItems,
  leagueId,
  leagueName,
  isBeginner,
  goal,
}: {
  data: DashboardResponse;
  tradeItems: BriefingItem[];
  leagueId: string;
  leagueName: string;
  isBeginner: boolean;
  goal: string | null | undefined;
}) {
  const query = `?name=${encodeURIComponent(leagueName)}`;
  const id = encodeURIComponent(leagueId);
  const deadlinePassed = Boolean(data.trade_window?.trade_deadline_passed);
  const pending = Boolean(data.trade_ideas_deferred) && tradeItems.length === 0;
  const goalLine = isBeginner ? tradesGoalLine(goal) : "";
  return (
    <section className="flex flex-col gap-2" aria-labelledby="trades-heading" data-testid="dashboard-trades-block">
      <SectionHeading
        id="trades-heading"
        action={
          isBeginner ? (
            <BeginnerHelp popover text={`${TRADES_BLOCK_COPY.beginnerExplainer}${goalLine ? ` ${goalLine}` : ""}`} />
          ) : undefined
        }
      >
        {TRADES_BLOCK_COPY.title}
      </SectionHeading>
      <Link
        href={`/trade-hub/${id}${query}`}
        className="glass-surface flex items-center justify-between gap-2 px-3 py-2 text-sm font-bold"
        style={{ minHeight: "var(--touch-target-min)", color: "inherit", textDecoration: "none" }}
      >
        <span style={{ color: tradeItems.length > 0 && !deadlinePassed ? "var(--color-text-primary)" : "var(--color-text-secondary)" }}>
          {tradeIdeasLine(tradeItems.length, deadlinePassed, pending)}
        </span>
        <span style={{ color: "var(--color-accent)" }}>{TRADES_BLOCK_COPY.link} →</span>
      </Link>
    </section>
  );
}

/** Secondary modules, collapsed by default (native disclosure: no JS state). */
export function DashboardMore({ children }: { children: ReactNode }) {
  return (
    <details className="glass-surface" data-testid="dashboard-more">
      <summary
        className="flex items-center justify-between px-4 text-sm font-bold uppercase cursor-pointer"
        style={{ minHeight: "var(--touch-target-min)", letterSpacing: "0.02em" }}
      >
        <span>More</span>
        <span className="text-xs font-normal normal-case" style={{ color: "var(--color-text-muted)" }}>
          League activity, games, settings
        </span>
      </summary>
      <div className="flex flex-col gap-6 px-4 pb-4 pt-2">{children}</div>
    </details>
  );
}
