import Link from "next/link";
import type { ReactNode } from "react";

import type { BriefingItem, DashboardResponse } from "@/lib/api";
import { AccentCard } from "@/components/AccentCard";
import { ToneBadge } from "@/components/ToneBadge";
import { BeginnerHelp } from "@/components/BeginnerHelp";
import { SectionHeading } from "@/components/SectionHeading";
import { CompactModule } from "@/components/ui/CompactModule";
import { LinkModule } from "@/components/ui/ModuleTemplates";
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
                <span className="min-w-0 flex-1 flex flex-col items-start gap-1">
                  <ToneBadge label={entry.badge} color="var(--color-danger)" />
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
                <span aria-hidden="true" data-row-arrow style={{ color: "var(--color-accent)" }}>
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
  const stateTone = deadlinePassed ? "muted" : tradeItems.length > 0 ? "action" : "muted";
  return (
    <section className="flex flex-col gap-2" data-testid="dashboard-trades-block">
      <LinkModule
        title={TRADES_BLOCK_COPY.title}
        href={`/trade-hub/${id}${query}`}
        tone="action"
        parts={[
          { key: "ideas", text: tradeIdeasLine(tradeItems.length, deadlinePassed, pending), tone: stateTone, strong: tradeItems.length > 0 && !deadlinePassed },
          deadline ? { key: "deadline", text: `Deadline ${deadline.value}`, tone: deadline.tone === "risk" ? "danger" : "muted" } : null,
          { key: "link", text: TRADES_BLOCK_COPY.link, tone: "accent" },
        ]}
      />
      {isBeginner ? (
        <BeginnerHelp popover label="trade ideas" text={`${TRADES_BLOCK_COPY.beginnerExplainer}${goalLine ? ` ${goalLine}` : ""}`} />
      ) : null}
    </section>
  );
}

/** Secondary modules (league activity, the mini-games, league type), one compact module, mounted only when opened. */
export function DashboardMore({ children }: { children: ReactNode }) {
  return (
    <CompactModule
      id="today.more"
      title="More"
      testId="dashboard-more"
      tone="muted"
      parts={[
        { key: "a", text: "League activity" },
        { key: "g", text: "2 mini-games" },
        { key: "t", text: "League type" },
      ]}
    >
      {children}
    </CompactModule>
  );
}
