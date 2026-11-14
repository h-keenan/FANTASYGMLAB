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
import { CompactModule } from "@/components/ui/CompactModule";
import { StatusHeader } from "@/components/ui/StatusHeader";
import { MatchupHeroCard } from "@/components/ui/MatchupModule";
import { simMatchupCardModel } from "@/lib/matchupModules";
import { buildSimStatusHeader, simHomeAttentionItems } from "@/lib/statusHeader";
import { simLeagueParts } from "@/lib/simSummaries";
import { useSimAutoSet } from "@/components/useSimAutoSet";
import { ClaimSheet } from "@/components/SimGameTeam";
import { SkeletonCard } from "@/components/Skeleton";
import { ToneBadge } from "@/components/ToneBadge";
import { api } from "@/lib/api";
import {
  simChecklistProgress,
  simChecklistTarget,
  simHomeDynastyLine,
  simChecklistTone,
  simProjText,
  simFmtRecord,
  simRowEdge,
  simSeasonText,
  simSlotLabels,
  type SimGamePlayer,
  type SimHomeMatchup,
  type SimHomeResponse,
  type SimWaiverClaim,
  simGameReasonMessage,
} from "@/lib/simGame";
import type { SimTab } from "@/lib/simGameFlow";

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
  const [failed, setFailed] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [claiming, setClaiming] = useState<{ player: SimGamePlayer; roster: SimGamePlayer[] } | null>(null);
  const teamId = ctx.game.you?.team_id;
  const wide = useSimWide();

  useEffect(() => {
    let cancelled = false;
    api
      .getSimHome(gameId)
      .then((body) => {
        if (cancelled) return;
        if (body.reason) setFailed(body.message || simGameReasonMessage(body.reason, body));
        else {
          setFailed(null);
          // A card the server could not build comes back null with its name in `errors`: hide it, keep the page.
          setHome({ ...body, standings: body.standings ?? undefined, league: body.league ?? undefined, hot_cold: body.hot_cold ?? undefined });
        }
      })
      .catch((error: unknown) => {
        const status = (error as { status?: number } | null)?.status ?? 0;
        if (!cancelled) setFailed(status >= 500 ? "The server hit a problem building Home. Your other tabs still work. Try again in a moment." : "Check your connection and try again.");
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
    return <EmptyState title="Could not load your home screen" subtitle={failed} actionLabel="Try again" onAction={() => { setFailed(null); setAttempt((n) => n + 1); }} />;
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
  const sheet = claiming ? (
    <ClaimSheet ctx={ctx} player={claiming.player} roster={claiming.roster} onClose={() => setClaiming(null)} onClaimed={(next) => { setClaims(next); ctx.bump(); }} />
  ) : null;

  const header = <SimStatusHeader home={home} onTab={onTab} />;

  // Phones: one scrolling column. This week's cards first, then a collapsed "League" section (standings, hot/cold,
  // league moves), so there is no second tab strip under the bottom bar's tabs. Desktop keeps one two-column page.
  if (!wide) {
    return (
      <div className="flex flex-col gap-3" data-testid="sim-home">
        {header}
        {home.matchup ? <SimMatchupCard ctx={ctx} matchup={home.matchup} onTab={onTab} /> : null}
        <SimChecklistCard home={home} onTab={onTab} onAuto={home.matchup && !home.matchup.bye ? auto.run : undefined} autoBusy={auto.busy} optimal={auto.optimal} />
        <SimReservesStrip home={home} onTab={onTab} />
        <SimInboxCard ctx={ctx} inbox={home.inbox} onTab={onTab} />
        <SimWaiverCard ctx={ctx} suggestions={home.waiver_suggestions ?? []} onClaim={claim} onTab={onTab} />
        <SimByeCard ctx={ctx} alerts={home.bye_alerts ?? []} onTab={onTab} onClaim={claim} />
        <SimInjuriesCard ctx={ctx} injuries={home.injuries ?? []} />
        <CompactModule id="home.league" testId="home-league-section" title="League" parts={simLeagueParts(home.standings, home.league?.recent.length ?? 0, home.hot_cold ? { hot: home.hot_cold.hot.length, cold: home.hot_cold.cold.length } : undefined)}>
          <div className="flex flex-col gap-3">
            <SimStandingsCard standings={home.standings} onTab={onTab} />
            <SimHotColdCard ctx={ctx} hotCold={home.hot_cold} onClaim={claim} />
            <SimLeagueMovesCard league={home.league} names={names} onTab={onTab} />
          </div>
        </CompactModule>
        {sheet}
      </div>
    );
  }
  return (
    <div className="flex flex-col gap-4 lg:grid lg:grid-cols-2 lg:items-start" data-testid="sim-home">
      <div className="flex flex-col gap-4">
        {header}
        {home.matchup ? <SimMatchupCard ctx={ctx} matchup={home.matchup} onTab={onTab} /> : null}
        <SimReservesStrip home={home} onTab={onTab} />
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

/**
 * The players-first status header on Home (ring = this week's win chance, record, three mini stats, the starters and
 * targets that need you as player rows, the first unfinished checklist step as the one action). The cards below keep
 * every detail. Projection and ADP only; the sim never shows its internal rating.
 */
function SimStatusHeader({ home, onTab }: { home: SimHomeResponse; onTab: (tab: SimTab) => void }) {
  const mine = home.standings?.rows.find((r) => r.is_you);
  const record = home.matchup?.you_record ?? (mine ? { wins: mine.wins, losses: mine.losses, ties: mine.ties } : null);
  const next = (home.checklist ?? []).find((item) => !item.done && simChecklistTarget(item));
  const model = buildSimStatusHeader({
    week: home.week ?? home.matchup?.week ?? null,
    seasonLabel: home.dynasty ? simSeasonText(home.dynasty) : null,
    record: record ? simFmtRecord(record) : null,
    rank: home.standings?.your_rank ?? mine?.rank ?? null,
    teams: home.standings?.rows.length ?? null,
    inPlayoffs: home.standings ? home.standings.in_playoffs : null,
    opponentName: home.matchup?.opponent?.name ?? null,
    winProb: home.matchup && !home.matchup.bye ? (home.matchup.win_prob ?? null) : null,
    bye: Boolean(home.matchup?.bye),
    injuredCount: (home.injuries ?? []).length,
    offers: home.inbox?.count ?? 0,
    waiverTargets: (home.waiver_suggestions ?? []).length,
    attention: simHomeAttentionItems(home),
    next: next ? { label: next.label, actionKey: simChecklistTarget(next) as string } : null,
  });
  return <StatusHeader model={model} attentionTitle="Needs your attention" onAction={(key) => onTab(key as SimTab)} testId="sim-status-header" />;
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
  const youProj = matchup.you_projection ?? 0;
  const oppProj = matchup.opp_projection ?? 0;
  const labels = simSlotLabels(matchup.rows);
  const flagged = (matchup.you_flagged ?? 0) + (matchup.opp_flagged ?? 0);
  return <MatchupBody ctx={ctx} matchup={matchup} onTab={onTab} prob={prob} youProj={youProj} oppProj={oppProj} labels={labels} flagged={flagged} />;
}

function MatchupBody({ ctx, matchup, onTab, prob, youProj, oppProj, labels, flagged }: { ctx: SimCtx; matchup: SimHomeMatchup; onTab: (tab: SimTab) => void; prob: number; youProj: number; oppProj: number; labels: string[]; flagged: number }) {
  const you = ctx.game.you;
  const opp = matchup.opponent!;
  const wide = useSimWide();
  const [showLineups, setShowLineups] = useState<boolean | null>(null);
  const lineupsOpen = showLineups ?? wide;
  const cardModel = simMatchupCardModel({
    week: matchup.week,
    playoff: matchup.kind === "playoff",
    opponentName: opp.name,
    youName: "You",
    youProjection: youProj,
    oppProjection: oppProj,
    winProb: prob,
    rows: matchup.rows,
  });
  return (
    <MatchupHeroCard
      model={cardModel}
      testId="sim-matchup-hero"
      onOpenPlayer={(p) => {
        const hit = matchup.rows.flatMap((r) => [r.you, r.opp]).find((pl) => pl && pl.name === p.name);
        if (hit) ctx.openPlayer(hit);
      }}
      action={<Button fullWidth onClick={() => onTab("team")}>Set lineup</Button>}
    >
      <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-2 text-xs" style={{ color: "var(--color-text-muted)" }}>
        <div className="flex min-w-0 flex-col items-center gap-1 text-center">
          <SimTeamLink teamId={you?.team_id} name={you?.name ?? "You"} isYou size={28} stacked />
          <span>{matchup.you_record ? simFmtRecord(matchup.you_record) : ""}</span>
        </div>
        <span className="font-extrabold">VS</span>
        <div className="flex min-w-0 flex-col items-center gap-1 text-center">
          <SimTeamLink teamId={opp.team_id} name={opp.name} size={28} stacked />
          <span>{opp.record ? simFmtRecord(opp.record) : ""} · {opp.persona.label}</span>
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
    </MatchupHeroCard>
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
      <span className="text-sm font-extrabold tabular-nums leading-none" style={{ color: player.status === "healthy" ? tint : "var(--color-text-muted)" }}>{simProjText(player)}</span>
      <div className="w-full min-w-0"><SimMiniPlayer player={player} align={align} onOpen={ctx.openPlayer} size={24} wrap /></div>
    </div>
  );
}

/** One tappable line for dynasty / IR games (season, picks, IR and taxi use); nothing in redraft. */
function SimReservesStrip({ home, onTab }: { home: SimHomeResponse; onTab: (tab: SimTab) => void }) {
  const line = simHomeDynastyLine(home);
  if (!line) return null;
  return (
    <button
      type="button"
      className="flex w-full items-center justify-between gap-2 px-3 text-left text-xs font-bold"
      style={{ minHeight: "var(--touch-target-min)", borderRadius: "var(--radius-card, 12px)", border: "var(--border-width-default) solid var(--color-border)", background: "var(--color-surface)", color: "var(--color-text-secondary)" }}
      onClick={() => onTab("team")}
      data-testid="home-reserves-strip"
    >
      <span className="min-w-0">{line}</span>
      <span className="shrink-0" style={{ color: "var(--color-accent)" }}>Team</span>
    </button>
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
              <button type="button" className="flex w-full items-center gap-3 py-2 text-left" style={{ minHeight: "var(--touch-target-min)" }} onClick={() => { const t = simChecklistTarget(item); if (t) onTab(t as SimTab); }}>
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
