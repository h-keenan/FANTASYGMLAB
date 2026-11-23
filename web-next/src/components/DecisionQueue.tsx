"use client";

import Link from "next/link";

import { ButtonLink } from "@/components/Button";
import { EmptyState } from "@/components/EmptyState";
import { FreeLimitNote } from "@/components/FreeLimitNote";
import { GamePlanCard } from "@/components/GamePlanCard";
import { SectionHeading } from "@/components/SectionHeading";
import { SkeletonCard } from "@/components/Skeleton";
import { ExpandRow, ExpandRowGroup } from "@/components/ui/ExpandRow";
import { PlayerAvatarSlot } from "@/components/ui/PlayerAvatarSlot";
import { CompactPlayerCard } from "@/components/ui/CompactPlayerCard";
import { InfoMark } from "@/components/ui/InfoMark";
import { useExperienceCopy } from "@/context/ExperienceLevelContext";
import type { BriefingItem } from "@/lib/api";
import type { Decision, DecisionPlayer, DecisionSwap, DecisionQueue as Queue } from "@/lib/decisionQueue";
import { GAME_PLAN_INTERNAL_ROUTES, gamePlanTileHref } from "@/lib/gamePlanPresentation";
import { TRADES_BLOCK_COPY } from "@/lib/dashboardLayout";
import { thisWeekHref } from "@/lib/thisWeek";
import { matchupPlanParams, swapGainLabel, type TodayAction } from "@/lib/todayView";

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

/** The Matchup page with its lineup planner already on this swap (or on every suggested move when `swap` is null). */
export function swapHref(swap: Pick<DecisionSwap, "out" | "replacement"> | null, leagueId: string, leagueName: string): string {
  const params = new URLSearchParams({ name: leagueName, ...matchupPlanParams(swap) });
  return `/matchup/${encodeURIComponent(leagueId)}?${params.toString()}`;
}

const SWAP_TONE = { danger: "var(--color-danger)", warning: "var(--color-warning)" } as const;

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

/** One action as a one-line ExpandRow: avatar, a short reason, ONE button. The fuller reason and the players sit behind the row's tap. */
function ActionRow({ a, leagueId, leagueName, tradeHref }: { a: TodayAction<BriefingItem>; leagueId: string; leagueName: string; tradeHref: string }) {
  const d = a.decision;
  const href = a.swap ? swapHref(a.swap, leagueId, leagueName) : d ? (d.swaps.length > 0 ? swapHref(null, leagueId, leagueName) : decisionHref(d, leagueId, leagueName)) : tradeHref;
  const tone = SWAP_TONE[a.tone === "danger" ? "danger" : "warning"];
  const gain = a.swap ? swapGainLabel(a.swap) : null;
  const [first, ...others] = d?.players ?? [];
  return (
    <ExpandRow
      testId={`decision-${a.kind === "swap" ? "lineup" : a.kind}`}
      label={`${a.kind === "swap" ? "LINEUP" : (d?.label ?? "TRADE")}: ${a.reason}`}
      leading={a.player ? <PlayerAvatarSlot player={playerRef(a.player)} tier="row" nonInteractive="the row's toggle is the tap target" /> : <span aria-hidden="true" className="shrink-0 rounded-full" style={{ width: 10, height: 10, background: tone }} />}
      title={a.reason}
      caption={gain ? <span style={{ color: "var(--color-success)" }}>{gain} projected</span> : undefined}
      action={
        <ButtonLink href={href} variant="primary" size="sm" aria-label={`${a.button}: ${a.reason}`} data-testid="decision-primary">
          {a.button}
        </ButtonLink>
      }
    >
      {a.swap ? (
        <>
          {a.detail ? <p className="m-0 text-sm" style={{ color: "var(--color-text-secondary)" }}>{a.detail}</p> : null}
          {a.swap.replacement?.name ? <PlayerLine p={{ ...a.swap.replacement, note: "Best healthy replacement", stat: gain ? { value: gain, label: "GAIN" } : null }} /> : null}
        </>
      ) : d ? (
        <>
          {a.reason !== d.title ? (
            <p className="m-0 text-sm font-bold" data-testid="decision-full-title">
              {d.title}
            </p>
          ) : null}
          {d.why ? (
            <p className="m-0 text-sm" style={{ color: "var(--color-text-secondary)" }}>
              {d.why}
            </p>
          ) : d.summary ? (
            <p className="m-0 text-sm" style={{ color: "var(--color-text-secondary)" }}>
              {d.summary}
            </p>
          ) : null}
          {first ? <PlayerLine p={first} /> : null}
          {others.map((p) => (
            <PlayerLine key={p.id ?? p.name} p={p} />
          ))}
          {d.facts.length > 0 ? (
            <p className="m-0 text-xs font-bold" style={{ color: "var(--color-text-muted)" }}>
              {d.facts.join(" · ")}
            </p>
          ) : null}
          {d.item && d.kind !== "waiver" ? <GamePlanCard item={d.item} leagueId={leagueId} leagueName={leagueName} /> : null}
        </>
      ) : a.detail ? (
        <p className="m-0 text-sm" style={{ color: "var(--color-text-secondary)" }} data-testid="decision-trade-detail">{a.detail}</p>
      ) : null}
    </ExpandRow>
  );
}

/**
 * "Do this now" (docs/ui-patterns.md, "Decision Queue"): the lineup's swap stack first, then the other ranked decisions
 * (waivers, deadline, draft, injuries) as compact modules, the rest behind "See all (N)". The queue says "nothing needs
 * you" only when it has no decision at all. Ranking and dedupe are in lib/decisionQueue.ts. Mobile twin:
 * components/DecisionQueue.tsx.
 */
export function DecisionQueue({
  queue,
  actions,
  tradeHref,
  leagueId,
  leagueName,
  pending = false,
  emptyOverride,
  entitlement,
}: {
  queue: Queue<BriefingItem>;
  /** The ranked, capped rows (lib/todayView.ts todayActions): lineup fixes, waivers, deadline, injuries, the best trade. */
  actions: { rows: TodayAction<BriefingItem>[]; total: number };
  /** Where the best-trade row's button opens. */
  tradeHref: string;
  leagueId: string;
  leagueName: string;
  /** The matchup read has not settled: hold the place so nothing jumps when decisions land. */
  pending?: boolean;
  /** A server reason for an empty Today ("connect your account"), shown instead of the generic empty line. */
  emptyOverride?: string;
  /** The dashboard entitlement, for the Free-limit note (unchanged gating). */
  entitlement?: { is_premium: boolean; visible_count: number; hidden_count: number; free_limit?: number };
}) {
  const copy = useExperienceCopy();
  if (pending) {
    return (
      <section aria-busy="true" data-testid="decision-queue-loading">
        <SkeletonCard lines={3} style={{ minHeight: 120 }} />
      </section>
    );
  }
  const hidden = actions.total - actions.rows.length;
  const planHref = `/gm-plan/${encodeURIComponent(leagueId)}?name=${encodeURIComponent(leagueName)}`;
  return (
    <section className="flex flex-col gap-2" aria-labelledby="decision-queue-heading" data-testid="decision-queue" data-fgl-dashboard-useful="true" data-fgl-this-week="true">
      <SectionHeading
        id="decision-queue-heading"
        help={<InfoMark label="your game plan" lines={[copy.help("dashboardGamePlan"), actions.total === 0 && !emptyOverride ? copy.help("dashboardNothingUrgent") : null, actions.rows.some((a) => a.kind === "trade") && copy.isBeginner ? TRADES_BLOCK_COPY.beginnerExplainer : null]} beginnerOnly />}
      >
        {actions.total > 0 ? `Do this now · ${actions.total}` : "Do this now"}
      </SectionHeading>
      {actions.total === 0 ? (
        <EmptyState title={emptyOverride ?? queue.empty?.title ?? "Nothing needs you this week"} subtitle={emptyOverride ? undefined : (queue.empty?.detail ?? undefined)} />
      ) : (
        <ExpandRowGroup accent={actions.rows.some((a) => a.tone === "danger") ? "var(--color-danger)" : "var(--color-accent)"} testId="decision-rows">
          {actions.rows.map((a) => (
            <ActionRow key={a.key} a={a} leagueId={leagueId} leagueName={leagueName} tradeHref={tradeHref} />
          ))}
        </ExpandRowGroup>
      )}
      <Link href={planHref} aria-label={hidden > 0 ? `See all ${actions.total} in the GM Plan` : "Open the full GM Plan"} className="tap-link text-sm font-bold" style={{ minHeight: "var(--touch-target-min)", display: "inline-flex", alignItems: "center", color: "var(--color-accent)", textDecoration: "none" }} data-testid="decision-see-all">
        {hidden > 0 ? `See all (${actions.total}) →` : "Full GM Plan →"}
      </Link>
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
