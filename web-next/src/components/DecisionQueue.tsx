"use client";

import Link from "next/link";
import { useState } from "react";

import { BeginnerHelp } from "@/components/BeginnerHelp";
import { ButtonLink } from "@/components/Button";
import { EmptyState } from "@/components/EmptyState";
import { FreeLimitNote } from "@/components/FreeLimitNote";
import { GamePlanCard } from "@/components/GamePlanCard";
import { MotionIn } from "@/components/Motion";
import { SectionHeading } from "@/components/SectionHeading";
import { SkeletonCard } from "@/components/Skeleton";
import { CompactModule } from "@/components/ui/CompactModule";
import { CompactPlayerCard } from "@/components/ui/CompactPlayerCard";
import type { BriefingItem } from "@/lib/api";
import { decisionSummaryParts, seeAllLabel, type Decision, type DecisionPlayer, type DecisionQueue as Queue } from "@/lib/decisionQueue";
import { GAME_PLAN_INTERNAL_ROUTES, gamePlanTileHref } from "@/lib/gamePlanPresentation";
import { thisWeekHref } from "@/lib/thisWeek";

/** Where a decision's one primary action goes. Shared by the queue rows and the hero's next action. */
export function decisionHref(d: Pick<Decision<BriefingItem>, "primary" | "item">, leagueId: string, leagueName: string): string {
  const { target, playerId } = d.primary;
  const id = encodeURIComponent(leagueId);
  const query = `?name=${encodeURIComponent(leagueName)}`;
  if (target === "gm_plan") return `/gm-plan/${id}${query}`;
  if (target === "item") {
    const route = d.item ? (GAME_PLAN_INTERNAL_ROUTES[d.item.destination] ?? "gm-plan") : "gm-plan";
    return gamePlanTileHref(route, leagueId, leagueName, playerId ?? "");
  }
  return thisWeekHref(target, leagueId, leagueName, playerId ?? "");
}

const toneAccent = { danger: "danger", warning: "warning", accent: "accent", success: "success" } as const;

function playerRef(p: DecisionPlayer) {
  return { id: p.id, name: p.name, position: p.position, team: p.team, tier: p.tier };
}

function PlayerLine({ p }: { p: DecisionPlayer }) {
  return (
    <CompactPlayerCard
      player={playerRef(p)}
      detail={p.note}
      trailing={p.stat ? <span className="flex flex-col items-end"><span style={{ color: "var(--color-success)" }}>{p.stat.value}</span><span className="text-[0.6875rem] font-extrabold uppercase" style={{ color: "var(--color-text-muted)" }}>{p.stat.label}</span></span> : undefined}
      testId="decision-player"
    />
  );
}

function DecisionRow({ d, leagueId, leagueName }: { d: Decision<BriefingItem>; leagueId: string; leagueName: string }) {
  const [first, ...others] = d.players;
  const href = decisionHref(d, leagueId, leagueName);
  return (
    <CompactModule
      id={`today.decision.${d.key}`}
      persist={false}
      title={d.label}
      label={d.title}
      tone={toneAccent[d.tone]}
      parts={decisionSummaryParts(d)}
      testId={`decision-${d.kind}`}
      action={
        <ButtonLink href={href} variant="primary" size="sm" data-testid="decision-primary">
          {d.primary.label}
        </ButtonLink>
      }
      preview={first ? <PlayerLine p={first} /> : undefined}
    >
      {d.why ? (
        <p className="m-0 text-sm" style={{ color: "var(--color-text-secondary)" }}>
          {d.why}
        </p>
      ) : null}
      {others.map((p) => (
        <PlayerLine key={p.id ?? p.name} p={p} />
      ))}
      {d.facts.length > 0 ? (
        <p className="m-0 text-xs font-bold" style={{ color: "var(--color-text-muted)" }}>
          {d.facts.join(" · ")}
        </p>
      ) : null}
      {d.item && d.kind !== "waiver" ? <GamePlanCard item={d.item} leagueId={leagueId} leagueName={leagueName} /> : null}
    </CompactModule>
  );
}

/**
 * The Today Decision Queue (docs/ui-patterns.md, "Decision Queue"): at most three ranked decisions, each a CompactModule
 * with the shared player card, one primary action, and the reasons on expand; "See all (N)" opens the rest in place.
 * Ranking and dedupe are in lib/decisionQueue.ts. Mobile twin: components/DecisionQueue.tsx.
 */
export function DecisionQueue({
  queue,
  leagueId,
  leagueName,
  pending = false,
  emptyOverride,
  entitlement,
}: {
  queue: Queue<BriefingItem>;
  leagueId: string;
  leagueName: string;
  /** The matchup read has not settled: hold the place so nothing jumps when decisions land. */
  pending?: boolean;
  /** A server reason for an empty Today ("connect your account"), shown instead of the generic empty line. */
  emptyOverride?: string;
  /** The dashboard entitlement, for the Free-limit note (unchanged gating). */
  entitlement?: { is_premium: boolean; visible_count: number; hidden_count: number; free_limit?: number };
}) {
  const [open, setOpen] = useState(false);
  if (pending) {
    return (
      <section aria-busy="true" data-testid="decision-queue-loading">
        <SkeletonCard lines={3} style={{ minHeight: 120 }} />
      </section>
    );
  }
  const seeAll = seeAllLabel(queue, open);
  const shown = open ? queue.all : queue.visible;
  return (
    <section className="flex flex-col gap-2" aria-labelledby="decision-queue-heading" data-testid="decision-queue" data-fgl-dashboard-useful="true" data-fgl-this-week="true">
      <SectionHeading
        id="decision-queue-heading"
        size="compact"
        help={<BeginnerHelp popover label="your game plan" term="dashboardGamePlan" />}
        action={
          <Link href={`/gm-plan/${encodeURIComponent(leagueId)}?name=${encodeURIComponent(leagueName)}`} aria-label="Open the full GM Plan" className="tap-link text-sm font-bold shrink-0" style={{ color: "var(--color-accent)" }}>
            Full GM Plan →
          </Link>
        }
      >
        {queue.total > 0 ? `Do next · ${queue.total}` : "Do next"}
      </SectionHeading>
      {queue.total === 0 ? (
        <EmptyState title={emptyOverride ?? queue.empty?.title ?? "Nothing needs you this week"} subtitle={emptyOverride ? undefined : (queue.empty?.detail ?? undefined)}>
          {!emptyOverride ? <BeginnerHelp label="nothing urgent" term="dashboardNothingUrgent" className="mt-1" /> : null}
        </EmptyState>
      ) : (
        shown.map((d, i) => (
          <MotionIn key={d.key} index={i >= 3 ? i - 3 : 0} count={Math.max(1, shown.length)}>
            <DecisionRow d={d} leagueId={leagueId} leagueName={leagueName} />
          </MotionIn>
        ))
      )}
      {seeAll ? (
        <button type="button" onClick={() => setOpen(!open)} aria-expanded={open} className="tap-link text-sm font-bold" style={{ minHeight: "var(--touch-target-min)", color: "var(--color-accent)" }} data-testid="decision-see-all">
          {seeAll}
        </button>
      ) : null}
      {queue.proUpsell ? (
        <Link href="/premium" className="glass-surface flex items-center justify-between gap-2 px-3" style={{ minHeight: 44, border: "var(--border-width-default) solid var(--color-premium)", color: "inherit", textDecoration: "none" }} data-testid="more-moves-upsell">
          <span className="text-sm font-bold">
            {queue.proUpsell.hidden} more move{queue.proUpsell.hidden === 1 ? "" : "s"} on Pro
          </span>
          <span className="text-sm font-bold shrink-0" style={{ color: "var(--color-premium)" }}>
            Upgrade →
          </span>
        </Link>
      ) : entitlement ? (
        <FreeLimitNote kind="window" noun="next moves" limit={entitlement.free_limit} total={entitlement.visible_count + entitlement.hidden_count} shown={entitlement.visible_count} isPremium={entitlement.is_premium} />
      ) : null}
    </section>
  );
}
