import Link from "next/link";

import type { BriefingItem, DashboardResponse, ThisWeekRow } from "@/lib/api";
import { AccentCard } from "@/components/AccentCard";
import { BeginnerHelp } from "@/components/BeginnerHelp";
import { ButtonLink } from "@/components/Button";
import { FreeLimitNote } from "@/components/FreeLimitNote";
import { EmptyState } from "@/components/EmptyState";
import { GamePlanCard } from "@/components/GamePlanCard";
import { SectionHeading } from "@/components/SectionHeading";
import { SkeletonBlock } from "@/components/Skeleton";
import { ToneBadge } from "@/components/ToneBadge";
import { notReadyReasonMessage } from "@/lib/notReadyMessages";
import { thisWeekHref, thisWeekToneColor } from "@/lib/thisWeek";
import { buildTodayPlan, todayTitle } from "@/lib/todayPlan";

/**
 * The Dashboard's one hero module: "Today". It merges the former "This week"
 * strip (lineup / waiver / trade moves, or one next action offseason) and the
 * "Today" game-plan list into one schedule-aware order (lib/todayPlan.ts):
 * what matters today first (a risk lineup row, top-priority cards, today's
 * rows), then a quiet "Later this week" list. Items that used to appear in
 * both are shown once.
 */
export function TodayModule({
  data,
  leagueId,
  leagueName,
  now,
}: {
  data: DashboardResponse;
  leagueId: string;
  leagueName: string;
  /** Injected for tests; defaults to the current time. */
  now?: Date;
}) {
  const thisWeek = data.this_week ?? null;
  const plan = buildTodayPlan(thisWeek, data.items, now);
  const query = `?name=${encodeURIComponent(leagueName)}`;
  const nextAction = plan.nextAction;
  const hidden = data.entitlement.hidden_count;
  // The progressive first Dashboard pass has no trade verdict yet: reserve its
  // row's space so the full response fills it without a layout jump.
  const tradePending =
    Boolean(data.trade_ideas_deferred) && !nextAction && !thisWeek?.rows.some((row) => row.key === "trade");

  // Consecutive rows share one card; a top-priority card stands on its own.
  const groups: Array<{ cards: BriefingItem[] } | { rows: ThisWeekRow[] }> = [];
  for (const entry of plan.today) {
    const last = groups[groups.length - 1];
    if (entry.kind === "row") {
      if (last && "rows" in last) last.rows.push(entry.row);
      else groups.push({ rows: [entry.row] });
    } else {
      groups.push({ cards: [entry.item] });
    }
  }

  return (
    <section
      className="flex flex-col gap-3"
      aria-labelledby="game-plan-heading"
      data-fgl-dashboard-useful="true"
      data-fgl-this-week="true"
    >
      <SectionHeading
        id="game-plan-heading"
        action={
          <Link
            href={`/gm-plan/${encodeURIComponent(leagueId)}${query}`}
            aria-label="View all game plan items"
            className="tap-link text-sm font-bold shrink-0"
            style={{ color: "var(--color-accent)" }}
          >
            View All →
          </Link>
        }
      >
        {todayTitle(thisWeek)}
      </SectionHeading>
      <BeginnerHelp term="dashboardGamePlan" />
      <FreeLimitNote
        kind="window"
        noun="next moves"
        limit={data.entitlement.free_limit}
        total={data.entitlement.visible_count + data.entitlement.hidden_count}
        shown={data.entitlement.visible_count}
        isPremium={data.entitlement.is_premium}
      />

      {nextAction ? (
        <AccentCard accent="var(--color-accent)" compact>
          <h3 className="text-sm font-bold">{nextAction.headline}</h3>
          <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
            {nextAction.why}
          </p>
          <ButtonLink href={thisWeekHref(nextAction.route, leagueId, leagueName)} size="sm" className="mt-1">
            {nextAction.cta_label}
          </ButtonLink>
        </AccentCard>
      ) : null}

      {groups.map((group, index) =>
        "cards" in group ? (
          group.cards.map((item) => (
            <GamePlanCard key={item.recommendation_id || item.headline} item={item} leagueId={leagueId} leagueName={leagueName} />
          ))
        ) : (
          <AccentCard key={`rows-${index}`} accent="var(--color-accent)" compact>
            <MoveRows rows={group.rows} leagueId={leagueId} leagueName={leagueName} />
          </AccentCard>
        ),
      )}

      {plan.later.length > 0 ? (
        <div className="flex flex-col" data-fgl-today-later="true">
          <p className="m-0 text-xs uppercase font-bold" style={{ color: "var(--color-text-muted)", letterSpacing: "0.04em" }}>
            Later this week
          </p>
          <MoveRows rows={plan.later} leagueId={leagueId} leagueName={leagueName} />
        </div>
      ) : null}

      {tradePending ? <SkeletonBlock height={64} data-fgl-this-week-trade-pending="true" /> : null}

      {plan.isEmpty ? (
        <EmptyState
          title={
            notReadyReasonMessage(data.reason, {
              linkAccount: "Connect your Sleeper account to see your Game Plan.",
              emptyRoster: "Your roster doesn't have any players yet. This is expected if your draft is still in progress.",
            }) || "No urgent roster issues right now."
          }
        >
          {!data.reason ? <BeginnerHelp term="dashboardNothingUrgent" className="mt-1" /> : null}
        </EmptyState>
      ) : null}

      {hidden > 0 ? (
        <div
          className="p-4 flex flex-col gap-2 premium-glow-card"
          style={{ background: "var(--color-action-soft)", border: "var(--border-width-default) solid var(--color-premium)" }}
        >
          <p className="text-sm font-bold">
            {hidden} more move{hidden === 1 ? "" : "s"} available on Premium.
          </p>
          <ButtonLink href="/premium" variant="premium" size="sm">
            Upgrade →
          </ButtonLink>
        </div>
      ) : null}
    </section>
  );
}

function MoveRows({ rows, leagueId, leagueName }: { rows: ThisWeekRow[]; leagueId: string; leagueName: string }) {
  return (
    <ul className="flex flex-col" style={{ listStyle: "none", margin: 0, padding: 0 }}>
      {rows.map((row, index) => {
        const color = thisWeekToneColor(row.tone);
        const actionable = Boolean(row.cta_label && row.route);
        const body = (
          <>
            <ToneBadge label={row.status} color={color} />
            <span className="min-w-0 flex-1 flex flex-col">
              <span className="text-sm font-bold truncate">{row.headline}</span>
              <span
                className="text-xs"
                style={{
                  color: "var(--color-text-secondary)",
                  display: "-webkit-box",
                  WebkitLineClamp: 2,
                  WebkitBoxOrient: "vertical",
                  overflow: "hidden",
                }}
              >
                {row.why}
              </span>
            </span>
            {actionable ? (
              <span aria-hidden="true" style={{ color: "var(--color-accent)" }}>
                →
              </span>
            ) : null}
          </>
        );
        const rowStyle = index > 0 ? { borderTop: "1px solid var(--color-border)" } : undefined;
        return (
          <li key={row.key} style={rowStyle}>
            {actionable && row.route ? (
              <Link
                href={thisWeekHref(row.route, leagueId, leagueName, row.player_id)}
                aria-label={row.cta_label ?? undefined}
                className="flex items-center gap-2 py-2.5"
                style={{ minHeight: 44, color: "inherit", textDecoration: "none" }}
              >
                {body}
              </Link>
            ) : (
              <div className="flex items-center gap-2 py-2.5" style={{ minHeight: 44 }}>
                {body}
              </div>
            )}
          </li>
        );
      })}
    </ul>
  );
}
