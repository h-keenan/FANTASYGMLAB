"use client";

import { useEffect, useState } from "react";

import { AccentCard } from "@/components/AccentCard";
import { Button } from "@/components/Button";
import { EmptyState } from "@/components/EmptyState";
import { PositionBadge } from "@/components/PositionBadge";
import { SimGlyph } from "@/components/SimGlyph";
import {
  SimByeCard,
  SimHotColdCard,
  SimInboxCard,
  SimInjuriesCard,
  SimLeagueMovesCard,
  SimStandingsCard,
  SimWaiverCard,
} from "@/components/SimGameHomeCards";
import { SimMiniPlayer, SimSectionTitle, SimTeamLink, SimToneBadge, simToneColor, useSimWide, type SimCtx } from "@/components/SimGameParts";
import { PillRow } from "@/components/PillRow";
import { useSimAutoSet } from "@/components/useSimAutoSet";
import { ClaimSheet } from "@/components/SimGameTeam";
import { SkeletonCard } from "@/components/Skeleton";
import { ToneBadge } from "@/components/ToneBadge";
import { api } from "@/lib/api";
import {
  simChecklistProgress,
  simChecklistTone,
  simFmtPts,
  simFmtRecord,
  simRowEdge,
  simSlotLabels,
  simWinChanceLabel,
  simWinChanceTone,
  type SimGamePlayer,
  type SimHomeMatchup,
  type SimHomeResponse,
  type SimWaiverClaim,
} from "@/lib/simGame";
import type { SimTab } from "@/lib/simGameFlow";
import { SIM_HOME_VIEWS, type SimHomeView } from "@/lib/simLayout";

/**
 * The game's landing tab: this week's head-to-head, what to do this week,
 * bye-week cover, waiver targets for your holes, your trade inbox, injuries,
 * the standings and playoff picture, hot/cold players and what happened
 * around the league. Everything comes from one read-only call (GET /home);
 * each card links to the tab that handles it. Built from the main app's
 * shared pieces (AccentCard, SectionHeading, ToneBadge, PositionBadge).
 */
export function SimHomeTab({
  ctx,
  setClaims,
  onTab,
}: {
  ctx: SimCtx;
  setClaims: (claims: SimWaiverClaim[]) => void;
  onTab: (tab: SimTab) => void;
}) {
  const { gameId } = ctx;
  const [home, setHome] = useState<SimHomeResponse | null>(null);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [claiming, setClaiming] = useState<{ player: SimGamePlayer; roster: SimGamePlayer[] } | null>(null);
  const teamId = ctx.game.you?.team_id;
  const wide = useSimWide();
  const [view, setView] = useState<SimHomeView>("week");

  useEffect(() => {
    let cancelled = false;
    api
      .getSimHome(gameId)
      .then((body) => {
        if (cancelled) return;
        if (body.reason) setFailed(true);
        else {
          setFailed(false);
          setHome(body);
        }
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, [gameId, ctx.tick, attempt]);

  // Auto-set best lineup (shared hook): names the swap in a toast; the matchup card refreshes in place.
  const auto = useSimAutoSet(ctx, (applied) =>
    setHome((prev) =>
      prev?.matchup
        ? { ...prev, matchup: { ...prev.matchup, you_projection: applied.projected_total ?? prev.matchup.you_projection, rows: prev.matchup.rows.map((row, i) => ({ ...row, you: applied.slots?.[i]?.player ?? row.you })) } }
        : prev,
    ),
  );

  async function claim(player: SimGamePlayer) {
    let roster: SimGamePlayer[] = [];
    if (teamId) {
      try {
        roster = (await api.getSimGameTeam(gameId, teamId)).players ?? [];
      } catch {
        roster = [];
      }
    }
    setClaiming({ player, roster });
  }

  if (failed && !home) {
    return <EmptyState title="Could not load your home screen" subtitle="Check your connection and try again." actionLabel="Try again" onAction={() => { setFailed(false); setAttempt((n) => n + 1); }} />;
  }
  if (!home) {
    return (
      <div className="flex flex-col gap-3" aria-busy="true">
        <span className="sr-only" role="status">Loading your home screen</span>
        <SkeletonCard lines={6} />
        <SkeletonCard lines={4} />
      </div>
    );
  }

  const names = Object.fromEntries((home.standings?.rows ?? []).map((r) => [r.team_id, r.name]));
  const inboxCount = home.inbox?.count ?? 0;
  const sheet = claiming ? (
    <ClaimSheet ctx={ctx} player={claiming.player} roster={claiming.roster} onClose={() => setClaiming(null)} onClaimed={(next) => { setClaims(next); ctx.bump(); }} />
  ) : null;

  // Phones: two sub-views so the first screen is the week, not every card. Desktop keeps one two-column page.
  if (!wide) {
    return (
      <div className="flex flex-col gap-3" data-testid="sim-home">
        <PillRow
          ariaLabel="Home sections"
          variant="fill"
          options={SIM_HOME_VIEWS.map((v) => ({ label: v.value === "week" && inboxCount > 0 ? `${v.label} · ${inboxCount}` : v.label, value: v.value, glyph: v.glyph }))}
          active={view}
          onSelect={(value) => setView(value as SimHomeView)}
        />
        {view === "week" ? (
          <>
            {home.matchup ? <SimMatchupCard ctx={ctx} matchup={home.matchup} onTab={onTab} /> : null}
            <SimChecklistCard home={home} onTab={onTab} onAuto={home.matchup && !home.matchup.bye ? auto.run : undefined} autoBusy={auto.busy} optimal={auto.optimal} />
            <SimInboxCard ctx={ctx} inbox={home.inbox} onTab={onTab} />
            <SimWaiverCard ctx={ctx} suggestions={home.waiver_suggestions ?? []} onClaim={claim} onTab={onTab} />
            <SimByeCard ctx={ctx} alerts={home.bye_alerts ?? []} onTab={onTab} onClaim={claim} />
            <SimInjuriesCard ctx={ctx} injuries={home.injuries ?? []} />
          </>
        ) : (
          <>
            <SimStandingsCard standings={home.standings} onTab={onTab} />
            <SimHotColdCard ctx={ctx} hotCold={home.hot_cold} onClaim={claim} />
            <SimLeagueMovesCard league={home.league} names={names} onTab={onTab} />
          </>
        )}
        {sheet}
      </div>
    );
  }
  return (
    <div className="flex flex-col gap-4 lg:grid lg:grid-cols-2 lg:items-start" data-testid="sim-home">
      <div className="flex flex-col gap-4">
        {home.matchup ? <SimMatchupCard ctx={ctx} matchup={home.matchup} onTab={onTab} /> : null}
        <SimInjuriesCard ctx={ctx} injuries={home.injuries ?? []} />
        <SimStandingsCard standings={home.standings} onTab={onTab} />
        <SimHotColdCard ctx={ctx} hotCold={home.hot_cold} onClaim={claim} />
      </div>
      <div className="flex flex-col gap-4">
        <SimChecklistCard home={home} onTab={onTab} onAuto={home.matchup && !home.matchup.bye ? auto.run : undefined} autoBusy={auto.busy} optimal={auto.optimal} />
        <SimByeCard ctx={ctx} alerts={home.bye_alerts ?? []} onTab={onTab} onClaim={claim} />
        <SimWaiverCard ctx={ctx} suggestions={home.waiver_suggestions ?? []} onClaim={claim} onTab={onTab} />
        <SimInboxCard ctx={ctx} inbox={home.inbox} onTab={onTab} />
        <SimLeagueMovesCard league={home.league} names={names} onTab={onTab} />
      </div>
      {sheet}
    </div>
  );
}

function SimMatchupCard({ ctx, matchup, onTab }: { ctx: SimCtx; matchup: SimHomeMatchup; onTab: (tab: SimTab) => void }) {
  const opp = matchup.opponent;
  const week = matchup.week;
  if (matchup.bye || !opp) {
    return (
      <AccentCard accent="var(--color-warning)" as="section">
        <SimSectionTitle glyph="bye" tone="warning">Week {week} bye</SimSectionTitle>
        <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>You do not play this week. Use it to work the wire and your trades.</p>
      </AccentCard>
    );
  }
  const prob = matchup.win_prob ?? 0.5;
  const tone = simWinChanceTone(prob);
  const youProj = matchup.you_projection ?? 0;
  const oppProj = matchup.opp_projection ?? 0;
  const labels = simSlotLabels(matchup.rows);
  const flagged = (matchup.you_flagged ?? 0) + (matchup.opp_flagged ?? 0);
  return <MatchupBody ctx={ctx} matchup={matchup} onTab={onTab} prob={prob} tone={tone} youProj={youProj} oppProj={oppProj} labels={labels} flagged={flagged} />;
}

function MatchupBody({ ctx, matchup, onTab, prob, tone, youProj, oppProj, labels, flagged }: { ctx: SimCtx; matchup: SimHomeMatchup; onTab: (tab: SimTab) => void; prob: number; tone: ReturnType<typeof simWinChanceTone>; youProj: number; oppProj: number; labels: string[]; flagged: number }) {
  const you = ctx.game.you;
  const opp = matchup.opponent!;
  const week = matchup.week;
  const wide = useSimWide();
  const [showLineups, setShowLineups] = useState<boolean | null>(null);
  const lineupsOpen = showLineups ?? wide;
  return (
    <AccentCard accent="var(--color-accent)" glow as="section" className="min-w-0">
      <div className="flex items-center justify-between gap-2">
        <SimSectionTitle glyph="matchup" tone="accent">{matchup.kind === "playoff" ? "Playoff matchup" : `Week ${week} matchup`}</SimSectionTitle>
        <Button size="sm" variant="secondary" onClick={() => onTab("team")}>Set lineup</Button>
      </div>

      <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-2">
        <div className="flex min-w-0 flex-col items-center gap-1 text-center">
          <SimTeamLink teamId={you?.team_id} name={you?.name ?? "You"} isYou size={36} stacked />
          <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>{matchup.you_record ? simFmtRecord(matchup.you_record) : ""}</span>
        </div>
        <span className="text-xs font-extrabold" style={{ color: "var(--color-text-muted)" }}>VS</span>
        <div className="flex min-w-0 flex-col items-center gap-1 text-center">
          <SimTeamLink teamId={opp.team_id} name={opp.name} size={36} stacked />
          <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>{opp.record ? simFmtRecord(opp.record) : ""} · {opp.persona.label}</span>
        </div>
      </div>

      <div className="flex flex-col gap-1" data-testid="win-chance">
        <div className="flex items-end justify-between gap-2">
          <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>Your win chance</span>
          <span className="text-2xl font-extrabold tabular-nums leading-none" style={{ color: simToneColor(tone) }}>{simWinChanceLabel(prob)}</span>
        </div>
        <div className="h-2 w-full overflow-hidden" style={{ borderRadius: "var(--radius-pill)", background: "color-mix(in srgb, var(--color-danger) 28%, var(--color-surface-muted))" }} role="img" aria-label={`Win chance ${simWinChanceLabel(prob)}`}>
          <div className="h-full" style={{ width: `${Math.round(prob * 100)}%`, background: "var(--color-success)" }} />
        </div>
        <div className="flex items-center justify-between text-sm font-extrabold tabular-nums" data-testid="matchup-projections">
          <span style={{ color: youProj >= oppProj ? "var(--color-success)" : "var(--color-text-primary)" }} data-testid="your-projection">{simFmtPts(youProj)}</span>
          <span className="text-xs font-normal" style={{ color: "var(--color-text-muted)" }}>projected points</span>
          <span style={{ color: oppProj > youProj ? "var(--color-danger)" : "var(--color-text-primary)" }}>{simFmtPts(oppProj)}</span>
        </div>
      </div>

      {flagged > 0 ? (
        <p className="flex items-center gap-2 text-xs" style={{ color: "var(--color-warning)" }} role="status">
          <SimGlyph name="alert" size={14} />
          {(matchup.you_flagged ?? 0) > 0 ? `${matchup.you_flagged} of your starters are out or on bye. ` : ""}
          {(matchup.opp_flagged ?? 0) > 0 ? `${matchup.opp_flagged} of theirs ${matchup.opp_flagged === 1 ? "is" : "are"} too.` : ""}
        </p>
      ) : null}

      <button
        type="button"
        className="tap-link self-start text-xs font-bold"
        style={{ color: "var(--color-accent)", minHeight: "var(--touch-target-min)" }}
        aria-expanded={lineupsOpen}
        aria-controls="sim-matchup-lineups"
        onClick={() => setShowLineups(!lineupsOpen)}
      >
        {lineupsOpen ? "Hide lineups" : `Show lineups (${matchup.rows.length} slots)`}
      </button>
      {lineupsOpen ? (
        <div id="sim-matchup-lineups" className="flex flex-col gap-2">
          <ol className="flex flex-col" aria-label="Lineups head to head">
            {matchup.rows.map((row, index) => {
              const edge = simRowEdge(row);
              return (
                <li
                  key={`${row.slot}-${index}`}
                  className="grid grid-cols-[1fr_auto_1fr] items-center gap-1 py-1.5"
                  style={{ borderTop: "var(--border-width-default) solid var(--color-border)" }}
                >
                  <Side player={row.you} win={edge === "you"} lose={edge === "opp"} align="left" ctx={ctx} />
                  <span className="flex w-11 justify-center"><PositionBadge position={row.slot} label={labels[index]} /></span>
                  <Side player={row.opp} win={edge === "opp"} lose={edge === "you"} align="right" ctx={ctx} />
                </li>
              );
            })}
          </ol>
          <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>Their lineup is what their manager will start. Projections update when injuries or byes change.</p>
        </div>
      ) : null}
    </AccentCard>
  );
}

function Side({ player, win, lose, align, ctx }: { player: SimGamePlayer | null; win: boolean; lose: boolean; align: "left" | "right"; ctx: SimCtx }) {
  const tint = win ? "var(--color-success)" : lose ? "var(--color-danger)" : "var(--color-text-secondary)";
  const end = align === "right";
  if (!player) {
    return <span className={`text-xs ${end ? "text-right" : ""}`} style={{ color: "var(--color-text-muted)" }}>Empty</span>;
  }
  // Projection on its own line above the name so the name keeps the full cell width (two lines allowed).
  return (
    <div
      className={`flex min-w-0 flex-col gap-0.5 px-1.5 py-1 ${end ? "items-end" : "items-start"}`}
      style={{ borderRadius: "var(--radius-card, 12px)", background: win ? "color-mix(in srgb, var(--color-success) 9%, transparent)" : undefined }}
    >
      <span className="text-sm font-extrabold tabular-nums leading-none" style={{ color: player.status === "healthy" ? tint : "var(--color-text-muted)" }}>{simFmtPts(player.projection)}</span>
      <div className="w-full min-w-0"><SimMiniPlayer player={player} align={align} onOpen={ctx.openPlayer} size={24} wrap /></div>
    </div>
  );
}

function SimChecklistCard({ home, onTab, onAuto, autoBusy = false, optimal = false }: { home: SimHomeResponse; onTab: (tab: SimTab) => void; onAuto?: () => void; autoBusy?: boolean; optimal?: boolean }) {
  const items = home.checklist ?? [];
  const { done, total } = simChecklistProgress(items);
  const allDone = total > 0 && done === total;
  return (
    <AccentCard accent={allDone ? "var(--color-success)" : "var(--color-warning)"} as="section">
      <SimSectionTitle glyph="checklist" tone={allDone ? "success" : "warning"} action={<ToneBadge label={`${done}/${total} done`} color={allDone ? "var(--color-success)" : "var(--color-warning)"} />}>
        What to do this week
      </SimSectionTitle>
      <div className="h-1.5 w-full overflow-hidden" style={{ borderRadius: "var(--radius-pill)", background: "var(--color-surface-muted)" }} aria-hidden="true">
        <div className="h-full" style={{ width: total ? `${(done / total) * 100}%` : 0, background: allDone ? "var(--color-success)" : "var(--color-warning)" }} />
      </div>
      {onAuto ? (
        <Button variant="secondary" loading={autoBusy} disabled={optimal} onClick={onAuto} data-testid="auto-lineup">
          <SimGlyph name={optimal ? "check" : "spark"} size={16} />
          <span className="ml-2">{optimal ? "Lineup is optimal" : "Auto-set best lineup"}</span>
        </Button>
      ) : null}
      <ul className="flex flex-col" aria-label="This week's checklist">
        {items.map((item, index) => {
          const color = simToneColor(simChecklistTone(item.severity));
          return (
            <li key={item.id} style={index > 0 ? { borderTop: "var(--border-width-default) solid var(--color-border)" } : undefined}>
              <button type="button" className="flex w-full items-center gap-3 py-2 text-left" style={{ minHeight: "var(--touch-target-min)" }} onClick={() => onTab(item.target as SimTab)}>
                <span
                  className="flex h-7 w-7 shrink-0 items-center justify-center"
                  style={{ borderRadius: "50%", color: item.done ? "var(--color-on-accent)" : color, background: item.done ? "var(--color-success)" : `color-mix(in srgb, ${color} 16%, transparent)` }}
                  aria-hidden="true"
                >
                  <SimGlyph name={item.done ? "check" : item.severity === "accent" ? "trade" : "alert"} size={14} />
                </span>
                <span className="flex min-w-0 flex-1 flex-col">
                  <span className="text-sm font-bold" style={{ textDecoration: item.done ? "line-through" : undefined, color: item.done ? "var(--color-text-muted)" : undefined }}>{item.label}</span>
                  {item.done ? null : <span className="text-xs" style={{ color: "var(--color-text-secondary)" }}>{item.detail}</span>}
                </span>
                <SimToneBadge label={item.done ? "Done" : item.severity === "danger" ? "Fix" : item.severity === "accent" ? "New" : "To do"} tone={item.done ? "success" : simChecklistTone(item.severity)} />
              </button>
            </li>
          );
        })}
      </ul>
    </AccentCard>
  );
}
