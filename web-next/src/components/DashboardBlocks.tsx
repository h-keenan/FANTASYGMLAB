import Link from "next/link";
import { useState, type ReactNode } from "react";

import type { BriefingItem, DashboardResponse } from "@/lib/api";
import { AccentCard } from "@/components/AccentCard";
import { ToneBadge } from "@/components/ToneBadge";
import { BeginnerHelp } from "@/components/BeginnerHelp";
import { SectionHeading } from "@/components/SectionHeading";
import {
  deadlineChip,
  tradeIdeasLine,
  tradesGoalLine,
  TRADES_BLOCK_COPY,
  type DashboardAttentionEntry,
} from "@/lib/dashboardLayout";
import { GAME_PLAN_INTERNAL_ROUTES, gamePlanTileHref, resolveGamePlanTargetPlayerId } from "@/lib/gamePlanPresentation";
import { thisWeekHref } from "@/lib/thisWeek";

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
    <section className="flex flex-col gap-3" aria-labelledby="needs-attention-heading" data-testid="dashboard-needs-attention">
      <SectionHeading id="needs-attention-heading" size="compact">
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
                <span className="shrink-0 w-[5.5rem]">
                  <ToneBadge label={entry.badge} color="var(--color-danger)" />
                </span>
                <span className="min-w-0 flex-1 flex flex-col">
                  <span className="text-sm font-bold break-words">{entry.headline}</span>
                  <span
                    className="text-xs"
                    style={{
                      color: "var(--color-text-secondary)",
                      display: "-webkit-box",
                      WebkitLineClamp: 2,
                      WebkitBoxOrient: "vertical" as const,
                      overflow: "hidden",
                    }}
                  >
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
  deadlineInAttention = false,
}: {
  data: DashboardResponse;
  tradeItems: BriefingItem[];
  leagueId: string;
  leagueName: string;
  isBeginner: boolean;
  goal: string | null | undefined;
  /** "Needs attention" already lists a near deadline: don't repeat it here. */
  deadlineInAttention?: boolean;
}) {
  const query = `?name=${encodeURIComponent(leagueName)}`;
  const id = encodeURIComponent(leagueId);
  const deadlinePassed = Boolean(data.trade_window?.trade_deadline_passed);
  const pending = Boolean(data.trade_ideas_deferred) && tradeItems.length === 0;
  const goalLine = isBeginner ? tradesGoalLine(goal) : "";
  // The one home for the deadline: here, not also as a chip.
  const deadline = deadlineInAttention ? null : deadlineChip(data.trade_window);
  return (
    <section className="flex flex-col gap-3" aria-labelledby="trades-heading" data-testid="dashboard-trades-block">
      <SectionHeading
        id="trades-heading"
        size="compact"
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
        <span className="min-w-0 flex flex-col">
          <span style={{ color: tradeItems.length > 0 && !deadlinePassed ? "var(--color-text-primary)" : "var(--color-text-secondary)" }}>
            {tradeIdeasLine(tradeItems.length, deadlinePassed, pending)}
          </span>
          {deadline ? (
            <span className="text-xs font-normal" style={{ color: deadline.tone === "risk" ? "var(--color-danger)" : "var(--color-text-muted)" }}>
              Trade deadline: {deadline.value}
            </span>
          ) : null}
        </span>
        <span className="shrink-0" style={{ color: "var(--color-accent)" }}>{TRADES_BLOCK_COPY.link} →</span>
      </Link>
    </section>
  );
}

/** Secondary modules, collapsed by default (native disclosure: no JS state). */
export function DashboardMore({ children }: { children: ReactNode }) {
  // Collapsed content is mounted on first open, so its self-fetching cards
  // (daily games) cost nothing for the many visits that never expand it.
  const [opened, setOpened] = useState(false);
  return (
    <details className="glass-surface" data-testid="dashboard-more" onToggle={(event) => event.currentTarget.open && setOpened(true)}>
      <summary
        className="flex items-center justify-between gap-3 px-4 text-sm font-bold uppercase cursor-pointer"
        style={{ minHeight: "var(--touch-target-min)", letterSpacing: "0.02em" }}
      >
        <span className="shrink-0">More</span>
        <span className="min-w-0 truncate text-xs font-normal normal-case" style={{ color: "var(--color-text-muted)" }}>
          League activity, games, settings
        </span>
      </summary>
      <div className="flex flex-col gap-5 px-4 pb-4 pt-2">{opened ? children : null}</div>
    </details>
  );
}
