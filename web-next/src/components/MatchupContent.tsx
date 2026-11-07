"use client";

import { RangeCompare } from "@/components/RangeCompare";
import { RANGE_CAPTION, leanLabel, rangeDisplayRows } from "@/lib/startSitRange";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";

import type {
  MatchupPositionEdge,
  MatchupResponse,
  MatchupSide,
  MatchupSuggestedMove,
} from "@/lib/api";
import { Button } from "@/components/Button";
import { BeginnerHelp } from "@/components/BeginnerHelp";
import { PageTitle } from "@/components/PageTitle";
import { EmptyState } from "@/components/EmptyState";
import { reloadPage } from "@/components/ErrorState";
import { PillRow } from "@/components/PillRow";
import { NextSteps } from "@/components/NextSteps";
import { PlannerBar, SwapSheet, useLineupPlanner } from "@/components/MatchupPlanner";
import { PlayerAvatar } from "@/components/PlayerAvatar";
import { PlayerIdentityTrigger } from "@/components/PlayerIdentityTrigger";
import { PlayerInjuryBadge } from "@/components/PlayerInjuryBadge";
import { PositionBadge } from "@/components/PositionBadge";
import { SectionHeading } from "@/components/SectionHeading";
import { StatStrip } from "@/components/StatStrip";
import { TeamAvatar } from "@/components/TeamAvatar";
import { ToneBadge } from "@/components/ToneBadge";
import { WeatherReasonChip } from "@/components/WeatherReasonChip";
import { ValuesCredit } from "@/components/ValuesCredit";
import {
  edgeExplanation,
  formatSeasonValue,
  formatSigned,
  hasKickedOff,
  headToHeadShare,
  lineupTotals,
  rowWinner,
  lineupComparisonRows,
  lineupPlayerPoints,
  matchupActionLabel,
  matchupNextAction,
  matchupReasonMessage,
  matchupVerdict,
  moveOverLine,
  moveSlotLabel,
  recordLabel,
  slotDisplayLabel,
  winProbabilityUnavailableMessage,
  type LineupPlayer,
  type VerdictTone,
} from "@/lib/matchupPresentation";
import { emptySlotsOf, plannerBase, plannerOpponentPlayers, slotIndexFor, winPercent } from "@/lib/matchupPlanner";

/**
 * Weekly Matchup, laid out to the owner's concept (2026-10-21): header with
 * week + LIVE, scoreboard, Matchup Insights, Lineup Comparison with
 * Suggested | Actual tabs, and Suggested Moves. Every number is from
 * GET .../leagues/{id}/matchup (the same endpoint mobile reads); this file
 * only arranges it. The concept's own colors/chrome are mapped onto the
 * shared tokens and components (glass-surface cards, SnapshotTile,
 * PillRow, PositionBadge, ToneBadge, .winprob-bar-*).
 *
 * FantasyDesk can't set a Sleeper lineup, so the Suggested tab and the
 * moves list are a planner; the copy says so. "Edit lineup" turns the
 * user's own column into a swap planner (components/MatchupPlanner.tsx):
 * every number for an edited lineup comes from POST .../matchup/what-if.
 */

const MOVES_PREVIEW_COUNT = 3;

function toneColor(tone: VerdictTone): string {
  if (tone === "positive") return "var(--color-success)";
  if (tone === "risk") return "var(--color-danger)";
  return "var(--color-text-primary)";
}

function signedTone(value: number | null | undefined): "positive" | "risk" | "neutral" {
  if (value == null || Math.abs(value) < 0.05) return "neutral";
  return value > 0 ? "positive" : "risk";
}

function MatchupHeader({ week, live, leagueName }: { week: number | null; live: boolean; leagueName: string }) {
  return (
    <header className="flex items-baseline gap-3 flex-wrap">
      <PageTitle page="Matchup" leagueName={leagueName} />
      {week != null ? (
        <span className="text-sm font-bold" style={{ color: "var(--color-text-secondary)" }}>
          Week {week}
        </span>
      ) : null}
      {live ? (
        <span className="self-center" aria-label="Games in progress">
          <ToneBadge label="● Live" color="var(--color-success)" />
        </span>
      ) : null}
      <span className="ml-auto">
        <BeginnerHelp term="matchupIntro" />
      </span>
      <BeginnerHelp term="matchupWinProbability" />
    </header>
  );
}

function ScoreSide({
  side,
  mine,
  score,
  projected,
  kickedOff,
}: {
  side: MatchupSide;
  mine: boolean;
  score: number | null;
  projected: number | null;
  kickedOff: boolean;
}) {
  // Before any game kicks off, Sleeper's 0.0 isn't a score yet, so the
  // projection leads; once games start the real score leads.
  const headline = kickedOff && score != null ? score.toFixed(1) : projected != null ? projected.toFixed(1) : "—";
  const caption = kickedOff && score != null ? (projected != null ? `Proj ${projected.toFixed(1)}` : null) : "Projected";
  return (
    <div className="flex-1 flex flex-col items-center text-center gap-1 min-w-0">
      <TeamAvatar
        avatarUrl={side.avatar_url}
        size={56}
        ringColor={mine ? "var(--color-accent)" : "var(--color-border-strong)"}
      />
      <span className="text-sm font-bold break-words w-full" style={{ color: "var(--color-text-primary)" }}>
        {side.team_name}
      </span>
      <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
        {recordLabel(side)}
      </span>
      <span style={{ font: "var(--type-primary-metric)", color: "var(--color-text-primary)" }}>{headline}</span>
      {caption ? (
        <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          {caption}
        </span>
      ) : null}
    </div>
  );
}

function Scoreboard({ matchup }: { matchup: MatchupResponse }) {
  const mine = matchup.my_team!;
  const opponent = matchup.opponent!;
  const comparison = matchup.comparison!;
  const odds = matchup.win_probability;
  const hasOdds = odds?.available === true && odds.probability != null;
  const myPct = hasOdds ? Math.round(odds!.probability! * 100) : null;
  const myProjected = hasOdds ? (odds!.my_projected_total ?? null) : null;
  const opponentProjected = hasOdds ? (odds!.opponent_projected_total ?? null) : null;
  const projectedMargin = myProjected != null && opponentProjected != null ? myProjected - opponentProjected : null;
  const kickedOff = hasKickedOff(matchup);

  return (
    <section className="glass-surface flex flex-col gap-4 p-4" aria-label="Scoreboard">
      <div className="flex items-start gap-2">
        <ScoreSide
          side={mine}
          mine
          score={mine.has_live_data ? mine.real_points : null}
          projected={myProjected}
          kickedOff={kickedOff}
        />
        <span
          className="self-center text-xs font-extrabold"
          style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}
        >
          VS
        </span>
        <ScoreSide
          side={opponent}
          mine={false}
          score={opponent.has_live_data ? opponent.real_points : null}
          projected={opponentProjected}
          kickedOff={kickedOff}
        />
      </div>

      {hasOdds ? (
        <div className="flex flex-col gap-1.5">
          <div
            className="winprob-bar-track"
            role="img"
            aria-label={`Win probability: you ${myPct}%, opponent ${100 - myPct!}%.`}
          >
            <span className="winprob-bar-fill" style={{ width: `${myPct}%` }} aria-hidden="true" />
          </div>
          <div className="flex items-center justify-between">
            <span className="text-base font-extrabold" style={{ color: "var(--color-success)" }}>
              {myPct}%
            </span>
            <span
              className="uppercase"
              style={{
                font: "var(--type-supporting-metadata)",
                color: "var(--color-text-muted)",
                letterSpacing: "var(--letter-spacing-badge)",
              }}
            >
              Win probability
            </span>
            <span className="text-base font-extrabold" style={{ color: "var(--color-text-secondary)" }}>
              {100 - myPct!}%
            </span>
          </div>
        </div>
      ) : (
        <p className="text-xs text-center" style={{ color: "var(--color-text-muted)" }}>
          {winProbabilityUnavailableMessage(matchup)}
        </p>
      )}

      {/* Symmetric: each team's season value on the outside, the two
          matchup-level margins inside. */}
      <StatStrip
        columns={4}
        items={[
          { glyph: "starter", label: "Your value", value: formatSeasonValue(comparison.my_season_value) },
          {
            glyph: "power",
            label: "Proj margin",
            value: projectedMargin != null ? formatSigned(projectedMargin) : "—",
            tone: signedTone(projectedMargin),
          },
          { glyph: "starter", label: "Their value", value: formatSeasonValue(comparison.opponent_season_value) },
          {
            glyph: "franchise",
            label: "Value margin",
            value:
              comparison.margin === 0
                ? "0"
                : `${comparison.margin > 0 ? "+" : "-"}${formatSeasonValue(Math.abs(comparison.margin))}`,
            tone: comparison.edge === "you" ? "positive" : comparison.edge === "opponent" ? "risk" : "neutral",
          },
        ]}
      />
    </section>
  );
}

function EdgeArrow({ edge }: { edge: number }) {
  const tone = signedTone(edge);
  const color =
    tone === "positive" ? "var(--color-success)" : tone === "risk" ? "var(--color-danger)" : "var(--color-text-muted)";
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true" style={{ color }}>
      {tone === "neutral" ? (
        <path d="M3 7h8" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      ) : (
        <path
          d={tone === "positive" ? "M7 12V2M3 6l4-4 4 4" : "M7 2v10M3 8l4 4 4-4"}
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          fill="none"
        />
      )}
    </svg>
  );
}

function EdgeList({ edges }: { edges: MatchupPositionEdge[] }) {
  return (
    <ul className="flex flex-col" aria-label="Position edges">
      {edges.map((edge) => {
        const tone = signedTone(edge.edge);
        const color =
          tone === "positive"
            ? "var(--color-success)"
            : tone === "risk"
              ? "var(--color-danger)"
              : "var(--color-text-muted)";
        return (
          <li
            key={edge.position}
            className="flex items-center gap-2 py-1.5"
            style={{ borderBottom: "var(--border-width-default) solid var(--color-border)" }}
          >
            <EdgeArrow edge={edge.edge} />
            <PositionBadge position={edge.position} />
            <span className="ml-auto pl-3 text-sm font-extrabold tabular-nums" style={{ color }}>
              {formatSigned(edge.edge)}
            </span>
          </li>
        );
      })}
    </ul>
  );
}

function MatchupInsights({ matchup }: { matchup: MatchupResponse }) {
  const verdict = matchupVerdict(matchup);
  const actualEdges = matchup.position_edges?.actual ?? null;
  const edges = actualEdges ?? matchup.position_edges?.suggested ?? [];
  const explanation = edgeExplanation(edges);
  const basis = actualEdges
    ? hasKickedOff(matchup)
      ? "Position edges: your Sleeper lineups, real points for started games plus projections."
      : "Position edges: this week's projections for your Sleeper lineups."
    : "Position edges: projections for each team's suggested lineup (Sleeper lineups aren't posted yet).";

  return (
    <section className="glass-surface flex flex-col gap-3 p-4" aria-labelledby="matchup-insights-title">
      <SectionHeading id="matchup-insights-title">Matchup Insights</SectionHeading>
      <div className="grid grid-cols-[minmax(0,1fr)_auto] gap-4 items-start">
        <div className="flex flex-col gap-1.5 min-w-0">
          <p className="text-lg font-extrabold" style={{ color: toneColor(verdict.tone) }}>
            {verdict.headline}
          </p>
          {explanation ? (
            <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
              {explanation}
            </p>
          ) : (
            <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
              No position projections yet to compare.
            </p>
          )}
        </div>
        {edges.length ? <EdgeList edges={edges} /> : null}
      </div>
      <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
        {basis}
      </p>
    </section>
  );
}

type CellEmphasis = "win" | "lose" | "even";

function LineupCell({
  player,
  mine,
  emphasis,
  onEdit,
}: {
  player: LineupPlayer | "empty" | null;
  mine: boolean;
  emphasis: CellEmphasis;
  /** Planner mode: tapping the cell opens the swap sheet instead of Quick View. */
  onEdit?: () => void;
}) {
  if (player === null) return <div />;
  if (player === "empty") {
    const label = (
      <span className="text-xs italic truncate" style={{ color: onEdit ? "var(--color-accent)" : "var(--color-text-muted)" }}>
        {onEdit ? "Empty, tap to fill" : "Empty slot"}
      </span>
    );
    return onEdit ? (
      <button type="button" onClick={onEdit} className="flex items-center py-2 w-full text-left min-w-0">
        {label}
      </button>
    ) : (
      <div className={`flex items-center py-2 min-w-0 ${mine ? "" : "justify-end"}`}>{label}</div>
    );
  }
  const points = lineupPlayerPoints(player);
  const valueText = points.value != null ? points.value.toFixed(1) : points.note === "bye" ? null : "—";
  const reverse = mine ? "" : "flex-row-reverse";
  const body = (
    <>
      <span className="hidden min-[430px]:inline-flex shrink-0">
        <PlayerAvatar playerId={player.player_id} tier={player.tier} size={24} />
      </span>
      <span className={`flex flex-col min-w-0 flex-1 ${mine ? "" : "items-end text-right"}`}>
        <PlayerNameText
          name={player.name || "Unknown player"}
          className="text-[13px] font-bold w-full leading-tight"
          style={{ color: "var(--color-text-primary)" }}
        />
        <span className={`flex items-center gap-1 min-w-0 text-[11px] leading-tight ${mine ? "" : "flex-row-reverse"}`}>
          <span className="truncate" style={{ color: "var(--color-text-muted)" }}>
            {player.team || "FA"}
          </span>
          <PlayerInjuryBadge status={player.injury_label} />
        </span>
      </span>
      <span className={`shrink-0 w-[2.1rem] ${mine ? "text-right" : "text-left"}`}>
        {valueText ? (
          <span
            className="text-sm tabular-nums"
            style={{
              color: emphasis === "lose" ? "var(--color-text-muted)" : "var(--color-text-primary)",
              fontWeight: emphasis === "win" ? 800 : emphasis === "lose" ? 500 : 700,
            }}
            title={points.kind === "pts" ? "Real points" : "Projected points"}
          >
            {valueText}
          </span>
        ) : (
          <ToneBadge label="Bye" color="var(--color-warning)" size="xs" />
        )}
      </span>
    </>
  );
  const cls = `flex items-center gap-1 py-2 w-full min-w-0 ${reverse}`;
  return onEdit ? (
    <button
      type="button"
      onClick={onEdit}
      aria-label={`Swap ${player.name || "player"}`}
      className={`${cls} text-left`}
    >
      {body}
    </button>
  ) : (
    <PlayerIdentityTrigger identity={{ ...player, sourceLabel: "Matchup" }} className={cls}>
      {body}
    </PlayerIdentityTrigger>
  );
}

/** One thin edge-to-edge bar splitting the row's points between the sides. */
function HeadToHeadBar({ share }: { share: number | null }) {
  return (
    <span
      className="flex h-[3px] w-full"
      style={{ background: "var(--color-border)", borderRadius: "var(--radius-pill)", overflow: "hidden" }}
      aria-hidden="true"
    >
      {share != null ? (
        <>
          <span style={{ width: `${share}%`, background: "var(--color-accent)" }} />
          <span style={{ flex: 1, background: "var(--color-border-strong)" }} />
        </>
      ) : null}
    </span>
  );
}

function emphasisFor(winner: ReturnType<typeof rowWinner>, side: "mine" | "opponent"): CellEmphasis {
  if (winner == null || winner === "tie") return "even";
  return winner === side ? "win" : "lose";
}

type LineupView = "suggested" | "actual";

function LineupComparison({
  matchup,
  view,
  onViewChange,
  leagueId,
  planner,
}: {
  matchup: MatchupResponse;
  view: LineupView;
  onViewChange: (view: LineupView) => void;
  leagueId?: string;
  planner?: ReturnType<typeof useLineupPlanner>;
}) {
  const mine = matchup.my_team!;
  const opponent = matchup.opponent!;
  const bestBall = matchup.best_ball === true;
  const actual = bestBall || view === "actual";
  const plan = planner?.plan ?? null;
  const canPlan = Boolean(planner && leagueId && !bestBall && plannerBase(matchup, view));
  const [helpOpen, setHelpOpen] = useState(false);
  const rows = plan
    ? lineupComparisonRows(
        plan.starters ?? [],
        plannerOpponentPlayers(matchup),
        emptySlotsOf(plan.slots),
        opponent.has_live_data ? (opponent.real_empty_slots ?? []) : (opponent.open_slots ?? []),
      )
    : actual
    ? lineupComparisonRows(
        mine.has_live_data ? mine.real_starters : [],
        opponent.has_live_data ? opponent.real_starters : [],
        mine.real_empty_slots ?? [],
        opponent.real_empty_slots ?? [],
      )
    : lineupComparisonRows(mine.starters, opponent.starters);
  const totals = lineupTotals(rows);
  const pointsOf = (cell: LineupPlayer | "empty" | null) =>
    cell && cell !== "empty" ? lineupPlayerPoints(cell).value : null;
  const caption = plan
    ? "Tap one of your players to see who could take the slot. A planner only: make the final change in Sleeper."
    : actual
    ? "Lineups as set in Sleeper."
    : "Our best lineup for each team, run the same way for both sides. A planner only: set your lineup in Sleeper.";
  const marginTone =
    Math.abs(totals.margin) < 0.05 ? "var(--color-text-muted)" : totals.margin > 0 ? "var(--color-success)" : "var(--color-danger)";
  const gridCols = "grid-cols-[minmax(0,1fr)_2.75rem_minmax(0,1fr)]";

  return (
    <section className="glass-surface flex flex-col gap-2 p-3 sm:p-4" aria-labelledby="lineup-comparison-title">
      <div className="flex items-center justify-between gap-2">
        <SectionHeading id="lineup-comparison-title">Lineup Comparison</SectionHeading>
        <button
          type="button"
          aria-label={helpOpen ? "Hide explanation" : "How this works"}
          aria-expanded={helpOpen}
          onClick={() => setHelpOpen((v) => !v)}
          className="inline-flex items-center justify-center font-bold shrink-0 text-xs"
          style={{
            width: 22,
            height: 22,
            borderRadius: 9999,
            border: "var(--border-width-default) solid var(--color-border)",
            color: "var(--color-accent)",
            lineHeight: 1,
          }}
        >
          ?
        </button>
      </div>
      {helpOpen ? (
        <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          {caption}
          {hasKickedOff(matchup) ? " Started games show real points; the rest show projections." : " Numbers are this week's projections."}
        </p>
      ) : null}
      {plan ? (
        <PlannerBar
          editing
          busy={plan.busy}
          error={plan.error ?? null}
          baselinePct={plan.baselinePct ?? null}
          currentPct={winPercent(plan.result?.win_probability)}
          leagueId={leagueId!}
          onEdit={() => planner!.start(view)}
          onReset={() => planner!.resetToSuggested()}
          onDone={() => planner!.exit()}
        />
      ) : bestBall ? null : (
        <div className="flex items-center justify-between gap-2">
          <PillRow
            options={[
              { label: "Suggested", value: "suggested" },
              { label: "Actual", value: "actual" },
            ]}
            active={view}
            onSelect={(value) => onViewChange(value as LineupView)}
          />
          {canPlan ? (
            <Button variant="secondary" size="sm" onClick={() => planner!.start(view)}>
              Edit lineup
            </Button>
          ) : null}
        </div>
      )}

      {rows.length === 0 ? (
        <p className="text-sm py-4 text-center" style={{ color: "var(--color-text-muted)" }}>
          {actual
            ? "Sleeper hasn't posted lineups for this week yet."
            : "No startable players on either roster right now."}
        </p>
      ) : (
        <div role="table" aria-label={actual ? "Actual lineups" : "Suggested lineups"} className="flex flex-col">
          <div role="row" className={`grid ${gridCols} gap-1 items-end pb-1 text-[11px] font-bold uppercase tracking-wide`}>
            <span role="columnheader" className="truncate" style={{ color: "var(--color-accent)" }}>
              {mine.team_name || "You"}
            </span>
            <span />
            <span role="columnheader" className="truncate text-right" style={{ color: "var(--color-text-muted)" }}>
              {opponent.team_name || "Opponent"}
            </span>
          </div>
          {rows.map((row, index) => {
            const emptyOrdinal =
              row.mine === "empty"
                ? rows.slice(0, index).filter((r) => r.slot === row.slot && r.mine === "empty").length
                : 0;
            const editIndex = plan ? slotIndexFor(plan.slots, row.mine, row.slot, emptyOrdinal) : -1;
            const myPts = pointsOf(row.mine);
            const theirPts = pointsOf(row.opponent);
            const winner = rowWinner(myPts, theirPts);
            return (
              <div
                role="row"
                key={`${row.slot}-${index}`}
                className="flex flex-col"
              >
                <div className={`grid ${gridCols} gap-1 items-center`}>
                  <div role="cell" className="min-w-0">
                    <LineupCell
                      player={row.mine}
                      mine
                      emphasis={emphasisFor(winner, "mine")}
                      onEdit={plan && editIndex >= 0 ? () => void planner!.openSlot(editIndex) : undefined}
                    />
                  </div>
                  <div role="cell" className="flex items-center justify-center">
                    <PositionBadge position={row.slot} />
                  </div>
                  <div role="cell" className="min-w-0">
                    <LineupCell player={row.opponent} mine={false} emphasis={emphasisFor(winner, "opponent")} />
                  </div>
                </div>
                <HeadToHeadBar share={headToHeadShare(myPts, theirPts)} />
              </div>
            );
          })}
          <div
            role="row"
            className="grid grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] gap-2 items-center pt-3"
          >
            <span role="cell" className="flex items-baseline gap-1.5 min-w-0">
              <span className="text-[11px] font-bold uppercase tracking-wide" style={{ color: "var(--color-text-muted)" }}>
                Total
              </span>
              <span className="text-base font-extrabold tabular-nums" style={{ color: "var(--color-text-primary)" }}>
                {totals.mine.toFixed(1)}
              </span>
            </span>
            <span role="cell">
              <ToneBadge
                label={Math.abs(totals.margin) < 0.05 ? "Even" : formatSigned(totals.margin)}
                color={marginTone}
                title="Your margin over this lineup's total"
              />
            </span>
            <span role="cell" className="flex items-baseline justify-end gap-1.5 min-w-0">
              <span className="text-base font-extrabold tabular-nums" style={{ color: "var(--color-text-primary)" }}>
                {totals.opponent.toFixed(1)}
              </span>
              <span className="text-[11px] font-bold uppercase tracking-wide" style={{ color: "var(--color-text-muted)" }}>
                Total
              </span>
            </span>
          </div>
        </div>
      )}
    </section>
  );
}

function MoveCard({ move, slotLabel }: { move: MatchupSuggestedMove; slotLabel: string }) {
  const tone = signedTone(move.gain);
  const gainColor =
    tone === "positive" ? "var(--color-success)" : tone === "risk" ? "var(--color-danger)" : "var(--color-text-muted)";
  return (
    <li
      className="flex flex-col gap-2 p-3"
      style={{ border: "var(--border-width-default) solid var(--color-border)", background: "var(--color-muted-soft)" }}
    >
      <div className="flex items-center gap-3">
      <PlayerIdentityTrigger
        identity={{
          player_id: move.start.player_id ?? "",
          name: move.start.name,
          position: move.start.position,
          team: move.start.team,
          tier: move.start.tier,
          sourceLabel: "Matchup",
        }}
        className="flex-1 flex items-center gap-3 min-w-0"
      >
        <span className="inline-flex shrink-0">
          <PlayerAvatar playerId={move.start.player_id} tier={move.start.tier} size={40} />
        </span>
        <div className="flex flex-col gap-0.5 min-w-0">
          <span className="flex items-center gap-2">
            <PositionBadge position={move.slot} label={slotLabel} />
            <span className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
              {move.start.points != null ? `Proj ${move.start.points.toFixed(1)}` : move.start_note || "No projection yet"}
            </span>
          </span>
          <span className="text-sm font-bold" style={{ color: "var(--color-text-primary)" }}>
            <span style={{ color: "var(--color-success)" }}>Start</span> {move.start.name || "Unknown player"}
          </span>
          <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
            {moveOverLine(move)}
          </span>
          <WeatherReasonChip notes={move.weather_notes?.filter((note) => note.applied)} />
        </div>
      </PlayerIdentityTrigger>
      <div className="flex flex-col items-center gap-1 shrink-0">
        <div
          className="flex flex-col items-center px-2.5 py-1.5"
          style={{
            background: `color-mix(in srgb, ${gainColor} 12%, transparent)`,
            border: `1px solid color-mix(in srgb, ${gainColor} 35%, transparent)`,
          }}
        >
          <span className="text-base font-extrabold tabular-nums" style={{ color: gainColor }}>
            {move.gain != null ? formatSigned(move.gain) : "—"}
          </span>
          <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
            Proj pts
          </span>
        </div>
        {move.locked ? <ToneBadge label="Locked" color="var(--color-text-muted)" /> : null}
      </div>
      </div>
      {move.range?.lean ? (
        <p className="text-xs" style={{ color: "var(--color-text-secondary)" }} data-testid="range-lean">
          <span className="font-bold uppercase" style={{ color: "var(--color-accent)", letterSpacing: "var(--letter-spacing-badge)" }}>
            {leanLabel(move.range.lean.kind)}
          </span>
          {" · "}
          {move.range.lean.why}
        </p>
      ) : null}
      <details className="text-xs">
        <summary className="cursor-pointer font-bold" style={{ color: "var(--color-text-muted)" }}>
          Weekly range
        </summary>
        <div className="pt-2">
          <RangeCompare
            rows={rangeDisplayRows(
              [
                { key: "start", label: "Start", range: move.range?.start ?? null },
                { key: "over", label: "Over", range: move.range?.over ?? null },
              ],
              move.range?.lean?.favors ?? null,
            )}
            lean={move.range?.lean ?? null}
            hideLean
            hideCaption
          />
        </div>
      </details>
    </li>
  );
}

function SuggestedMoves({ matchup }: { matchup: MatchupResponse }) {
  const [expanded, setExpanded] = useState(false);
  const moves = matchup.suggested_moves ?? null;
  const actualStarters = matchup.my_team?.real_starters ?? [];
  const shown = moves ? (expanded ? moves : moves.slice(0, MOVES_PREVIEW_COUNT)) : [];
  const hiddenCount = moves ? moves.length - MOVES_PREVIEW_COUNT : 0;

  return (
    <section className="glass-surface flex flex-col gap-3 p-4" aria-labelledby="suggested-moves-title">
      <div className="flex items-center justify-between gap-3">
        <SectionHeading id="suggested-moves-title">Suggested Moves</SectionHeading>
        {hiddenCount > 0 ? (
          <button
            type="button"
            onClick={() => setExpanded((open) => !open)}
            aria-expanded={expanded}
            className="text-xs font-bold"
            style={{ color: "var(--color-accent)" }}
          >
            {expanded ? "Show fewer" : `View all (${moves!.length})`}
          </button>
        ) : null}
      </div>
      {moves === null ? (
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
          Suggested moves appear once Sleeper has your lineup for this week.
        </p>
      ) : moves.length === 0 ? (
        <EmptyState title="Your Sleeper lineup already matches our suggested lineup." />
      ) : (
        <ul className="flex flex-col gap-2">
          {shown.map((move) => (
            <MoveCard
              key={`${move.start.player_id}-${move.slot}`}
              move={move}
              slotLabel={moveSlotLabel(move, actualStarters)}
            />
          ))}
        </ul>
      )}
      <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
        {RANGE_CAPTION} Weather shows only when it changes a projection.
      </p>
      <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
        The suggested lineup ranks by this week&apos;s projected points (season-long value only breaks ties or fills in where a projection is missing); gains are projected points. FantasyDesk
        can&apos;t change your Sleeper lineup, so make any swap in Sleeper.
      </p>
    </section>
  );
}

import { GuillotineCard, useGuillotine } from "@/components/GuillotineCard";
import { PlayerNameText } from "@/components/PlayerNameText";

export function MatchupContent({
  leagueName,
  matchup,
  leagueId,
  lens = "Dynasty",
}: {
  leagueName: string;
  matchup: MatchupResponse;
  leagueId?: string;
  lens?: string;
}) {
  const router = useRouter();
  const guillotineData = useGuillotine(leagueId, lens);
  const guillotine = guillotineData?.is_guillotine ? guillotineData : null;
  const ready = matchup.ok && matchup.my_team && matchup.opponent && matchup.comparison;
  const defaultView: LineupView = matchup.my_team?.has_live_data ? "actual" : "suggested";
  const [view, setView] = useState<LineupView>(defaultView);
  const planner = useLineupPlanner(leagueId ?? "", lens, matchup);
  const edited = planner.plan?.result;
  // While planning, the scoreboard and position edges show the edited
  // lineup (the API's numbers), everything else stays the real matchup.
  const shown = useMemo<MatchupResponse>(
    () =>
      edited?.win_probability
        ? {
            ...matchup,
            win_probability: edited.win_probability,
            position_edges: {
              actual: edited.position_edges ?? null,
              suggested: edited.position_edges ?? [],
            },
          }
        : matchup,
    [matchup, edited],
  );

  if (guillotine) {
    // No head-to-head in guillotine leagues: survival replaces win probability.
    return (
      <main className="flex-1 flex flex-col gap-4 px-4 py-3 max-w-3xl w-full mx-auto">
        <MatchupHeader week={guillotine.week ?? matchup.week} live={false} leagueName={leagueName} />
        <GuillotineCard data={guillotine} />
      </main>
    );
  }

  if (!ready) {
    const next = matchupNextAction(matchup.reason);
    const onNext = () => {
      if (next.action === "retry") return reloadPage();
      if (next.action === "connect" || !leagueId) return router.push("/connect-league");
      return router.push(`/dashboard/${encodeURIComponent(leagueId)}?name=${encodeURIComponent(leagueName)}`);
    };
    return (
      <main className="flex-1 flex flex-col gap-3 px-4 py-3 max-w-3xl w-full mx-auto">
        <MatchupHeader week={matchup.week} live={false} leagueName={leagueName} />
        <EmptyState
          title={matchupReasonMessage(matchup.reason)}
          subtitle={next.subtitle}
          actionLabel={matchupActionLabel(next.action)}
          onAction={onNext}
        />
      </main>
    );
  }

  return (
    <main className="flex-1 flex flex-col gap-4 px-4 py-3 max-w-3xl w-full mx-auto">
      <MatchupHeader week={matchup.week} live={matchup.game_state === "live"} leagueName={leagueName} />
      <Scoreboard matchup={shown} />
      {matchup.unmapped_players && matchup.unmapped_players.length > 0 ? (
        <p className="m-0 text-xs" style={{ color: "var(--color-text-muted)" }} data-testid="unmapped-starters">
          Not matched to a FantasyDesk player, so left out of the lineups and win odds:{" "}
          {matchup.unmapped_players.map((p) => `${p.name} (${p.fantasy_team})`).join(", ")}.
        </p>
      ) : null}
      <MatchupInsights matchup={shown} />
      <LineupComparison
        matchup={matchup}
        view={view}
        onViewChange={setView}
        leagueId={leagueId}
        planner={leagueId ? planner : undefined}
      />
      {planner.sheet && planner.plan ? (
        <SwapSheet
          sheet={planner.sheet}
          slot={planner.plan.slots[planner.sheet.index]?.slot ?? ""}
          onPick={planner.pick}
          onClose={planner.closeSheet}
        />
      ) : null}
      {matchup.best_ball ? (
        // Best ball: Sleeper sets both lineups from the highest weekly
        // scorers, so there is no suggested lineup or start/sit call.
        <p className="glass-surface text-sm p-4" style={{ color: "var(--color-text-secondary)" }}>
          {matchup.lineup_advice_message}
        </p>
      ) : (
        <SuggestedMoves matchup={matchup} />
      )}
      {leagueId ? (
        <NextSteps
          title="Fix a weak spot"
          steps={["waivers", "trade-hub", "my-team"]}
          leagueId={leagueId}
          leagueName={leagueName}
        />
      ) : null}
      <ValuesCredit />
    </main>
  );
}
