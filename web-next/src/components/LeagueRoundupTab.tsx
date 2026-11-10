"use client";

import { useEffect, useState } from "react";

import { AccentCard } from "@/components/AccentCard";
import { ButtonLink } from "@/components/Button";
import { EmptyState } from "@/components/EmptyState";
import { PillRow, TabStack } from "@/components/PillRow";
import { PositionBadge } from "@/components/PositionBadge";
import { SectionHeading } from "@/components/SectionHeading";
import { SkeletonBlock } from "@/components/Skeleton";
import { api, type RoundupResponse, type RoundupSwap, type WeeklyRoundup } from "@/lib/api";
import { trackUse } from "@/lib/analytics";
import {
  PREDICTABILITY_LABEL,
  formatPoints,
  predictabilityColorVar,
  regretBarPercent,
  roundupReasonMessage,
  roundupWeeks,
  swapLine,
} from "@/lib/roundupPresentation";

/**
 * League Recaps > Roundup: your lineup against the best lineup you could have
 * set, for a completed week (GET .../roundup, modules/weekly_roundup.py).
 * Starters vs optimal, each missed swap with a foreseeable / coin flip /
 * unforeseeable tag, a takeaway, and the season bench-regret tally. Free
 * accounts get the headline numbers and the single biggest swap; Pro gets
 * the rest (the server withholds it). Mirrors mobile's RoundupPanel.
 */
export function LeagueRoundupTab({ leagueId, initialWeek }: { leagueId: string; initialWeek?: number }) {
  const [week, setWeek] = useState<number | undefined>(initialWeek);
  const [attempt, setAttempt] = useState(0);
  const key = `${leagueId}|${week ?? "latest"}|${attempt}`;
  // The latest settled request, tagged with its key: "loading" is derived (no
  // setState inside the effect) and a stale response never overwrites a newer one.
  const [settled, setSettled] = useState<{ key: string; data?: RoundupResponse; error?: string } | null>(null);
  const [lastData, setLastData] = useState<RoundupResponse | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .getLeagueRoundup(leagueId, week)
      .then((response) => {
        if (cancelled) return;
        setSettled({ key, data: response });
        setLastData(response);
      })
      .catch((err) => {
        if (!cancelled) setSettled({ key, error: err instanceof Error ? err.message : "Could not load your roundup." });
      });
    return () => {
      cancelled = true;
    };
  }, [leagueId, week, key]);

  const loading = settled?.key !== key;
  const data = settled?.key === key && settled.data ? settled.data : lastData;
  const error = settled?.key === key ? (settled.error ?? null) : null;

  if (error && !data) {
    return (
      <EmptyState
        title="Could not load your roundup"
        subtitle={error}
        actionLabel="Try again"
        onAction={() => setAttempt((n) => n + 1)}
      />
    );
  }
  if (!data) {
    return (
      <div className="flex flex-col gap-3" role="status" aria-label="Loading roundup">
        <SkeletonBlock height={28} width="50%" />
        <SkeletonBlock height={120} />
        <SkeletonBlock height={160} />
      </div>
    );
  }
  if (!data.roundup) {
    const message = roundupReasonMessage(data.reason);
    return <EmptyState title={message.title} subtitle={message.subtitle} />;
  }

  const weeks = roundupWeeks(data.max_completed_week);
  const selected = data.week;
  return (
    <div className="flex flex-col gap-4" style={{ opacity: loading ? 0.6 : 1 }}>
      {weeks.length > 1 ? (
        <TabStack>
          <PillRow
            ariaLabel="Roundup week"
            variant="scroll"
            options={weeks.map((w) => ({ label: `Wk ${w}`, value: String(w) }))}
            active={String(selected)}
            onSelect={(value) => setWeek(Number(value))}
          />
        </TabStack>
      ) : null}
      <RoundupSummary roundup={data.roundup} />
      <SwapsSection roundup={data.roundup} isPremium={data.is_premium} />
      {data.is_premium && data.roundup.lineup.length > 0 ? <LineupSection roundup={data.roundup} /> : null}
      {data.is_premium && data.season ? <SeasonSection season={data.season} /> : null}
      {!data.is_premium && data.upsell ? (
        <AccentCard accent="var(--color-premium)" as="div" className="premium-glow-card">
          <p className="text-sm font-bold">{data.upsell.title}</p>
          <p className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
            {data.upsell.body}
          </p>
          <ButtonLink href="/premium" variant="premium" size="sm" onClick={() => trackUse("weekly_roundup", "upsell_tapped", { leagueId, tier: "free" })}>
            Upgrade to Pro →
          </ButtonLink>
        </AccentCard>
      ) : null}
      <p className="text-xs" style={{ color: "var(--color-text-muted)" }} data-testid="roundup-method">
        {data.method}
      </p>
    </div>
  );
}

function RoundupSummary({ roundup }: { roundup: WeeklyRoundup }) {
  return (
    <AccentCard accent="var(--color-accent)" as="section">
      <SectionHeading kicker="Weekly roundup">{`Week ${roundup.week}`}</SectionHeading>
      <div className="grid grid-cols-3 gap-3 text-center">
        <Stat label="You scored" value={formatPoints(roundup.actual_points)} />
        <Stat label="Best possible" value={formatPoints(roundup.optimal_points)} />
        <Stat label="Left on bench" value={formatPoints(roundup.left_on_bench)} color={roundup.left_on_bench >= 3 ? "var(--color-danger)" : "var(--color-success)"} />
      </div>
      <p className="text-sm" style={{ color: "var(--color-text-primary)" }}>
        {roundup.takeaway}
      </p>
    </AccentCard>
  );
}

function Stat({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-xl font-extrabold" style={{ color: color ?? "var(--color-text-primary)" }}>
        {value}
      </span>
      <span className="text-xs uppercase" style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}>
        {label}
      </span>
    </div>
  );
}

function SwapsSection({ roundup, isPremium }: { roundup: WeeklyRoundup; isPremium: boolean }) {
  if (roundup.swaps.length === 0) {
    return (
      <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
        No swaps would have gained meaningful points this week.
      </p>
    );
  }
  const hidden = Math.max(0, (roundup.swaps_total ?? roundup.swaps.length) - roundup.swaps.length);
  return (
    <section className="flex flex-col gap-2" aria-label="Missed swaps">
      <SectionHeading>{isPremium ? "Missed swaps" : "Biggest miss"}</SectionHeading>
      {roundup.swaps.map((swap) => (
        <SwapCard key={`${swap.slot}-${swap.started.player_id}-${swap.benched.player_id}`} swap={swap} />
      ))}
      {hidden > 0 ? (
        <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          {hidden} more missed swap{hidden === 1 ? "" : "s"} with Pro.
        </p>
      ) : null}
    </section>
  );
}

function SwapCard({ swap }: { swap: RoundupSwap }) {
  const accent = predictabilityColorVar(swap.predictability);
  return (
    <AccentCard accent={accent} compact as="article">
      <div className="flex items-center justify-between gap-2">
        <span
          className="text-xs font-extrabold uppercase"
          style={{ color: accent, letterSpacing: "var(--letter-spacing-badge)" }}
          data-testid="swap-tag"
        >
          {PREDICTABILITY_LABEL[swap.predictability]}
        </span>
        <span className="text-sm font-extrabold" style={{ color: "var(--color-text-primary)" }}>
          +{formatPoints(swap.gain)} pts
        </span>
      </div>
      <p className="text-sm font-bold" style={{ color: "var(--color-text-primary)" }}>
        {swapLine(swap)}
      </p>
      <div className="flex items-center gap-2 text-xs" style={{ color: "var(--color-text-secondary)" }}>
        <PositionBadge position={swap.slot} />
        <span>{swap.reason}</span>
      </div>
      {swap.started_projection && swap.benched_projection ? (
        <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          Projected before the week: {swap.started.name} {formatPoints(swap.started_projection.points)}, {swap.benched.name}{" "}
          {formatPoints(swap.benched_projection.points)}
        </p>
      ) : null}
    </AccentCard>
  );
}

function LineupSection({ roundup }: { roundup: WeeklyRoundup }) {
  return (
    <section className="flex flex-col gap-2" aria-label="Starters versus optimal lineup">
      <SectionHeading>Your lineup vs the best one</SectionHeading>
      <div className="glass-surface flex flex-col p-3 gap-1">
        <div className="grid grid-cols-[3.5rem_1fr_1fr] gap-2 text-xs uppercase" style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}>
          <span>Slot</span>
          <span>You started</span>
          <span>Best</span>
        </div>
        {roundup.lineup.map((row, index) => {
          const changed = row.actual.player_id !== row.optimal.player_id;
          return (
            <div key={`${row.slot}-${index}`} className="grid grid-cols-[3.5rem_1fr_1fr] gap-2 items-center text-sm">
              <PositionBadge position={row.slot} />
              <span style={{ color: changed ? "var(--color-text-secondary)" : "var(--color-text-primary)" }}>
                {row.actual.player_id ? `${row.actual.name} ${formatPoints(row.actual.points)}` : "Empty"}
              </span>
              <span className="font-bold" style={{ color: changed ? "var(--color-success)" : "var(--color-text-primary)" }}>
                {row.optimal.player_id ? `${row.optimal.name} ${formatPoints(row.optimal.points)}` : "Empty"}
              </span>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function SeasonSection({ season }: { season: NonNullable<RoundupResponse["season"]> }) {
  const worst = Math.max(0, ...season.weeks.map((w) => w.left_on_bench));
  return (
    <section className="flex flex-col gap-2" aria-label="Season bench regret">
      <SectionHeading kicker="Season to date">Bench regret</SectionHeading>
      <AccentCard accent="var(--color-diagnostic)" as="div">
        <p className="text-sm" style={{ color: "var(--color-text-primary)" }} data-testid="season-summary">
          {season.summary}
        </p>
        <div className="flex flex-col gap-1">
          {season.weeks.map((w) => (
            <div key={w.week} className="grid grid-cols-[2.5rem_1fr_3rem] items-center gap-2 text-xs">
              <span style={{ color: "var(--color-text-muted)" }}>Wk {w.week}</span>
              <span className="h-2 rounded-full" style={{ background: "var(--color-surface-muted)" }}>
                <span
                  className="block h-2 rounded-full"
                  style={{ width: `${regretBarPercent(w.left_on_bench, worst)}%`, background: "var(--color-diagnostic)" }}
                />
              </span>
              <span className="text-right font-bold" style={{ color: "var(--color-text-primary)" }}>
                {formatPoints(w.left_on_bench)}
              </span>
            </div>
          ))}
        </div>
      </AccentCard>
    </section>
  );
}
