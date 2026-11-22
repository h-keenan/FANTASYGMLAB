"use client";

import Link from "next/link";
import { useState } from "react";

import { Button, ButtonLink } from "@/components/Button";
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
import { seeAllLabel, type Decision, type DecisionPlayer, type DecisionSwap, type DecisionQueue as Queue } from "@/lib/decisionQueue";
import { GAME_PLAN_INTERNAL_ROUTES, gamePlanTileHref } from "@/lib/gamePlanPresentation";
import { thisWeekHref } from "@/lib/thisWeek";
import { matchupPlanParams, swapGainLabel, swapReplacementLine, todayActionRow, todayFixAll } from "@/lib/todayView";

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
const SWAP_VISIBLE = 4;

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

/** One lineup problem: the starter as the shared player card (avatar, status, who to start instead, the projected gain) and the Swap. */
function SwapRow({ swap, href, first }: { swap: DecisionSwap; href: string; first: boolean }) {
  const out = swap.out;
  const into = swap.replacement;
  const gain = swapGainLabel(swap);
  const detail = (
    <>
      <span className="font-extrabold uppercase" style={{ color: SWAP_TONE[swap.tone] }} data-testid="swap-status">
        {swap.status}
      </span>
      <span aria-hidden="true"> → </span>
      {swapReplacementLine(swap)}
    </>
  );
  const gainFigure = gain ? (
    <span style={{ color: "var(--color-success)" }} aria-label={`${gain} projected points`}>
      {gain}
    </span>
  ) : undefined;
  return (
    <li className="flex items-center gap-2 py-1" style={first ? undefined : { borderTop: "var(--border-width-default) solid var(--color-border)" }} data-testid="swap-row">
      <span className="min-w-0 flex-1">
        {out ? (
          <CompactPlayerCard player={playerRef(out)} detail={detail} trailing={gainFigure} testId="swap-player" />
        ) : (
          <span className="flex items-center gap-2" style={{ minHeight: 40 }}>
            <span aria-hidden="true" className="flex shrink-0 items-center justify-center text-lg font-extrabold" style={{ width: 28, height: 28, borderRadius: "50%", border: "2px dashed var(--color-warning)", color: "var(--color-warning)" }}>
              +
            </span>
            <span className="flex min-w-0 flex-1 flex-col">
              <span className="text-sm font-bold">Empty starter slot</span>
              <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>{swapReplacementLine(swap)}</span>
            </span>
            {gainFigure ? <span className="shrink-0 text-sm font-extrabold tabular-nums">{gainFigure}</span> : null}
          </span>
        )}
      </span>
      <ButtonLink href={href} size="sm" variant="primary" aria-label={out ? `Swap ${out.name}${into?.name ? ` for ${into.name}` : ""}` : `Fill the empty slot${into?.name ? ` with ${into.name}` : ""}`} data-testid="swap-button">
        Swap
      </ButtonLink>
    </li>
  );
}

/**
 * The lineup row's detail (behind its tap): one row per lineup problem with its fix and a one-tap Swap, plus "Fix all N ·
 * +X proj". Swap opens the Matchup page's lineup planner already on that move (FantasyDesk plans, it cannot set a Sleeper
 * lineup). Locked players (game started) are never in `swaps`; see lib/decisionQueue.ts lineupSwaps.
 */
function SwapDetail({ d, leagueId, leagueName }: { d: Decision<BriefingItem>; leagueId: string; leagueName: string }) {
  const [all, setAll] = useState(false);
  const shown = all ? d.swaps : d.swaps.slice(0, SWAP_VISIBLE);
  const fixAll = todayFixAll(d.swaps);
  const hidden = d.swaps.length - shown.length;
  return (
    <div className="flex flex-col" data-testid="swap-stack">
      <ul className="m-0 flex list-none flex-col p-0">
        {shown.map((swap, i) => (
          <SwapRow key={swap.key} swap={swap} href={swapHref(swap, leagueId, leagueName)} first={i === 0} />
        ))}
      </ul>
      {hidden > 0 ? (
        <Button variant="ghost" size="sm" onClick={() => setAll(true)} data-testid="swap-more">
          +{hidden} more
        </Button>
      ) : null}
      {fixAll ? (
        <ButtonLink href={swapHref(null, leagueId, leagueName)} variant="primary" fullWidth data-testid="swap-fix-all">
          {fixAll.label}
        </ButtonLink>
      ) : null}
    </div>
  );
}

/**
 * One decision as a one-line ExpandRow: avatar, a short reason (lib/todayView.ts todayActionRow), one button. The full
 * reason, the other players and the briefing card sit behind the row's tap.
 */
function DecisionRow({ d, leagueId, leagueName }: { d: Decision<BriefingItem>; leagueId: string; leagueName: string }) {
  const row = todayActionRow(d);
  const href = d.swaps.length > 0 ? swapHref(d.swaps.length === 1 ? d.swaps[0] : null, leagueId, leagueName) : decisionHref(d, leagueId, leagueName);
  const [first, ...others] = d.players;
  return (
    <ExpandRow
      testId={`decision-${d.kind}`}
      label={`${d.label}: ${row.reason}`}
      leading={row.player ? <PlayerAvatarSlot player={playerRef(row.player)} tier="row" nonInteractive="the row's toggle is the tap target" /> : <span aria-hidden="true" className="shrink-0 rounded-full" style={{ width: 10, height: 10, background: SWAP_TONE[d.tone === "danger" ? "danger" : "warning"] }} />}
      title={row.reason}
      action={
        <ButtonLink href={href} variant="primary" size="sm" aria-label={`${row.button}: ${row.reason}`} data-testid="decision-primary">
          {row.button}
        </ButtonLink>
      }
    >
      {d.swaps.length > 0 ? (
        <SwapDetail d={d} leagueId={leagueId} leagueName={leagueName} />
      ) : (
        <>
          {row.reason !== d.title ? (
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
      )}
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
  const copy = useExperienceCopy();
  if (pending) {
    return (
      <section aria-busy="true" data-testid="decision-queue-loading">
        <SkeletonCard lines={3} style={{ minHeight: 120 }} />
      </section>
    );
  }
  const seeAll = seeAllLabel(queue, open);
  const shown = open ? queue.all : queue.visible;
  // The count is the number of rows (a lineup's swaps are one row).
  const count = queue.total;
  return (
    <section className="flex flex-col gap-2" aria-labelledby="decision-queue-heading" data-testid="decision-queue" data-fgl-dashboard-useful="true" data-fgl-this-week="true">
      <SectionHeading
        id="decision-queue-heading"
        help={<InfoMark label="your game plan" lines={[copy.help("dashboardGamePlan"), queue.total === 0 && !emptyOverride ? copy.help("dashboardNothingUrgent") : null]} beginnerOnly />}
        action={
          <Link href={`/gm-plan/${encodeURIComponent(leagueId)}?name=${encodeURIComponent(leagueName)}`} aria-label="Open the full GM Plan" className="tap-link text-sm font-bold shrink-0" style={{ color: "var(--color-accent)" }}>
            Full GM Plan →
          </Link>
        }
      >
        {queue.total > 0 ? `Do this now · ${count}` : "Do this now"}
      </SectionHeading>
      {queue.total === 0 ? (
        <EmptyState title={emptyOverride ?? queue.empty?.title ?? "Nothing needs you this week"} subtitle={emptyOverride ? undefined : (queue.empty?.detail ?? undefined)} />
      ) : (
        <ExpandRowGroup accent={shown.some((d) => d.tone === "danger") ? "var(--color-danger)" : "var(--color-accent)"} testId="decision-rows">
          {shown.map((d) => (
            <DecisionRow key={d.key} d={d} leagueId={leagueId} leagueName={leagueName} />
          ))}
        </ExpandRowGroup>
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
