import Link from "next/link";
import type { ReactNode } from "react";

import type { BriefingItem, DashboardResponse } from "@/lib/api";
import { BeginnerHelp } from "@/components/BeginnerHelp";
import { ButtonLink } from "@/components/Button";
import { GamePlanCard } from "@/components/GamePlanCard";
import { SectionHeading } from "@/components/SectionHeading";
import { SkeletonBlock } from "@/components/Skeleton";
import { buildNowChips, tradesGoalLine, TRADES_BLOCK_COPY, type DashboardNowChip } from "@/lib/dashboardLayout";
import { DeadlineCard } from "@/components/DeadlineCard";
import { DEADLINE_CARD_WEEKS } from "@/lib/deadlineMode";
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
 * "What matters now": a compact row of real status chips (lineup, trade
 * deadline, alerts, waivers). Each is one tap to the place that fixes it.
 * Renders nothing when there is no real status to show.
 */
export function DashboardNowStrip({
  data,
  leagueId,
  leagueName,
}: {
  data: DashboardResponse;
  leagueId: string;
  leagueName: string;
}) {
  const alertCount = data.items.filter((item) => item.category !== "top_priority").length;
  const chips = buildNowChips(data.this_week?.rows, data.trade_window, alertCount);
  if (chips.length === 0) return null;
  return (
    <section aria-label="What matters now" data-testid="dashboard-now-strip" className="grid grid-cols-2 gap-2">
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
 * The primary block: the best real trade idea (the engine's Top Trade
 * Opportunity, with its give/get package and verdict), one primary action
 * ("Analyze a trade") and one quiet link to the rest of the board.
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
  const holdRow = data.this_week?.rows.find((row) => row.key === "trade");
  const goalLine = isBeginner ? tradesGoalLine(goal) : "";
  return (
    <section className="flex flex-col gap-3" aria-labelledby="trades-heading" data-testid="dashboard-trades-block">
      <SectionHeading id="trades-heading">{TRADES_BLOCK_COPY.title}</SectionHeading>
      {isBeginner ? (
        <BeginnerHelp text={`${TRADES_BLOCK_COPY.beginnerExplainer}${goalLine ? ` ${goalLine}` : ""}`} />
      ) : null}
      <DeadlineCard
        window={data.trade_window}
        strategy={data.team_strategy}
        maxWeeksLeft={DEADLINE_CARD_WEEKS}
        href={`/trade-hub/${id}${query}`}
        ctaLabel="See deadline trade ideas"
      />
      {deadlinePassed ? (
        <p className="m-0 text-sm" style={{ color: "var(--color-text-secondary)" }}>
          {TRADES_BLOCK_COPY.deadlinePassed}
        </p>
      ) : tradeItems.length > 0 ? (
        tradeItems.slice(0, 3).map((item) => (
          <GamePlanCard key={item.recommendation_id || item.headline} item={item} leagueId={leagueId} leagueName={leagueName} />
        ))
      ) : pending ? (
        <SkeletonBlock height={96} data-fgl-this-week-trade-pending="true" />
      ) : (
        <p className="m-0 text-sm" style={{ color: "var(--color-text-secondary)" }}>
          {holdRow ? `${holdRow.headline}. ${holdRow.why}` : TRADES_BLOCK_COPY.empty}
        </p>
      )}
      <div className="flex items-center gap-4 flex-wrap">
        <ButtonLink href={`/trade-analyzer/${id}${query}`} size="sm">
          {TRADES_BLOCK_COPY.analyze}
        </ButtonLink>
        {deadlinePassed ? null : (
          <Link href={`/trade-hub/${id}${query}`} className="tap-link text-sm font-bold" style={{ color: "var(--color-accent)" }}>
            {TRADES_BLOCK_COPY.more} →
          </Link>
        )}
      </div>
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
