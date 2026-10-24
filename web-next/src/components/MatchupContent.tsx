"use client";

import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";

import type {
  MatchupPositionEdge,
  MatchupResponse,
  MatchupSide,
  MatchupSuggestedMove,
} from "@/lib/api";
import { BeginnerHelp } from "@/components/BeginnerHelp";
import { EmptyState } from "@/components/EmptyState";
import { reloadPage } from "@/components/ErrorState";
import { PillRow } from "@/components/PillRow";
import { PlannerBar, SwapSheet, useLineupPlanner } from "@/components/MatchupPlanner";
import { PlayerAvatar } from "@/components/PlayerAvatar";
import { PlayerIdentityTrigger } from "@/components/PlayerIdentityTrigger";
import { PlayerInjuryBadge } from "@/components/PlayerInjuryBadge";
import { PositionBadge } from "@/components/PositionBadge";
import { SectionHeading } from "@/components/SectionHeading";
import { StatStrip } from "@/components/StatStrip";
import { TeamAvatar } from "@/components/TeamAvatar";
import { ToneBadge } from "@/components/ToneBadge";
import { ValuesCredit } from "@/components/ValuesCredit";
import {
  edgeExplanation,
  formatSeasonValue,
  formatSigned,
  hasKickedOff,
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
      <h1 style={{ font: "var(--font-page-title)" }}>Matchup</h1>
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
      <span className="ml-auto text-xs break-words max-w-full" style={{ color: "var(--color-text-muted)" }}>
        {leagueName}
      </span>
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

function PointsBar({ value, max, mine }: { value: number | null; max: number; mine: boolean }) {
  const pct = value != null && max > 0 ? Math.max(0, Math.min(100, (value / max) * 100)) : 0;
  return (
    <span
      className="block h-1 w-full"
      style={{ background: "var(--color-border)", borderRadius: "var(--radius-pill)", overflow: "hidden" }}
      aria-hidden="true"
    >
      <span
        className="block h-full"
        style={{
          width: `${pct}%`,
          marginLeft: mine ? 0 : "auto",
          background: mine ? "var(--color-accent)" : "var(--color-text-muted)",
        }}
      />
    </span>
  );
}

function LineupCell({
  player,
  mine,
  maxValue,
  onEdit,
}: {
  player: LineupPlayer | "empty" | null;
  mine: boolean;
  maxValue: number;
  /** Planner mode: tapping the cell opens the swap sheet instead of Quick View. */
  onEdit?: () => void;
}) {
  if (player === null) return <div />;
  if (player === "empty") {
    const label = (
      <span className="text-xs italic" style={{ color: onEdit ? "var(--color-accent)" : "var(--color-text-muted)" }}>
        {onEdit ? "Empty slot, tap to fill" : "Empty slot"}
      </span>
    );
    return onEdit ? (
      <button type="button" onClick={onEdit} className="flex items-center py-2 w-full text-left">
        {label}
      </button>
    ) : (
      <div className={`flex items-center py-2 ${mine ? "" : "justify-end"}`}>{label}</div>
    );
  }
  const points = lineupPlayerPoints(player);
  const valueText = points.value != null ? points.value.toFixed(1) : points.note === "bye" ? null : "—";
  const reverse = mine ? "" : "flex-row-reverse";
  const body = (
    <>
      <span className="inline-flex shrink-0">
        <PlayerAvatar playerId={player.player_id} tier={player.tier} size={28} />
      </span>
      <div className={`flex-1 flex flex-col gap-1 min-w-0 ${mine ? "" : "items-end"}`}>
        {/* Name gets its own full-width line so it survives phone widths;
            team + number share the second line, the bar the third. */}
        <span
          className={`text-sm font-bold break-words w-full ${mine ? "" : "text-right"}`}
          style={{ color: "var(--color-text-primary)" }}
        >
          {player.name || "Unknown player"}
        </span>
        <div className={`flex items-center justify-between gap-1 w-full ${reverse}`}>
          <span className={`flex items-center gap-1 min-w-0 ${reverse}`}>
            <span className="text-xs break-words" style={{ color: "var(--color-text-muted)" }}>
              {player.team || "FA"}
            </span>
            <PlayerInjuryBadge status={player.injury_label} />
          </span>
          {valueText ? (
            <span
              className="text-sm font-extrabold tabular-nums shrink-0"
              style={{ color: points.kind === "pts" ? "var(--color-text-primary)" : "var(--color-text-secondary)" }}
              title={points.kind === "pts" ? "Real points" : "Projected points"}
            >
              {valueText}
            </span>
          ) : (
            <ToneBadge label="Bye" color="var(--color-warning)" />
          )}
        </div>
        <PointsBar value={points.value} max={maxValue} mine={mine} />
      </div>
    </>
  );
  return onEdit ? (
    <button
      type="button"
      onClick={onEdit}
      aria-label={`Swap ${player.name || "player"}`}
      className={`flex items-center gap-1.5 sm:gap-2 py-2 w-full text-left ${reverse}`}
    >
      {body}
    </button>
  ) : (
    <PlayerIdentityTrigger
      identity={{ ...player, sourceLabel: "Matchup" }}
      className={`flex items-center gap-1.5 sm:gap-2 py-2 w-full ${reverse}`}
    >
      {body}
    </PlayerIdentityTrigger>
  );
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
  const maxValue = Math.max(
    0,
    ...rows.flatMap((row) =>
      [row.mine, row.opponent].map((cell) =>
        cell && cell !== "empty" ? (lineupPlayerPoints(cell).value ?? 0) : 0,
      ),
    ),
  );
  const caption = plan
    ? "Tap one of your players to see who could take the slot. A planner only: make the final change in Sleeper."
    : actual
    ? "Lineups as set in Sleeper."
    : "Our best lineup for each team, run the same way for both sides. A planner only: set your lineup in Sleeper.";

  return (
    <section className="glass-surface flex flex-col gap-3 p-3 sm:p-4" aria-labelledby="lineup-comparison-title">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <SectionHeading id="lineup-comparison-title">Lineup Comparison</SectionHeading>
        {bestBall || plan ? null : (
        <PillRow
          options={[
            { label: "Suggested Lineup", value: "suggested" },
            { label: "Actual Lineup", value: "actual" },
          ]}
          active={view}
          onSelect={(value) => onViewChange(value as LineupView)}
        />
        )}
      </div>
      {canPlan || plan ? (
        <PlannerBar
          editing={Boolean(plan)}
          busy={plan?.busy ?? false}
          error={plan?.error ?? null}
          baselinePct={plan?.baselinePct ?? null}
          currentPct={winPercent(plan?.result?.win_probability)}
          leagueId={leagueId!}
          onEdit={() => planner!.start(view)}
          onReset={() => planner!.resetToSuggested()}
          onDone={() => planner!.exit()}
        />
      ) : null}
      <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
        {caption}
        {hasKickedOff(matchup) ? " Started games show real points; the rest show projections." : " Numbers are this week's projections."}
      </p>

      {rows.length === 0 ? (
        <p className="text-sm py-4 text-center" style={{ color: "var(--color-text-muted)" }}>
          {actual
            ? "Sleeper hasn't posted lineups for this week yet."
            : "No startable players on either roster right now."}
        </p>
      ) : (
        <div role="table" aria-label={actual ? "Actual lineups" : "Suggested lineups"} className="flex flex-col">
          {rows.map((row, index) => {
            const emptyOrdinal =
              row.mine === "empty"
                ? rows.slice(0, index).filter((r) => r.slot === row.slot && r.mine === "empty").length
                : 0;
            const editIndex = plan ? slotIndexFor(plan.slots, row.mine, row.slot, emptyOrdinal) : -1;
            return (
            <div
              role="row"
              key={`${row.slot}-${index}`}
              className="grid grid-cols-[minmax(0,1fr)_2.75rem_minmax(0,1fr)] gap-1.5 sm:gap-2 items-center"
              style={{ borderBottom: "var(--border-width-default) solid var(--color-border)" }}
            >
              <div role="cell" className="min-w-0">
                <LineupCell
                  player={row.mine}
                  mine
                  maxValue={maxValue}
                  onEdit={plan && editIndex >= 0 ? () => void planner!.openSlot(editIndex) : undefined}
                />
              </div>
              <div
                role="cell"
                className="self-stretch flex items-center justify-center"
              >
                <PositionBadge position={row.slot} />
              </div>
              <div role="cell" className="min-w-0">
                <LineupCell player={row.opponent} mine={false} maxValue={maxValue} />
              </div>
            </div>
            );
          })}
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
      className="flex items-center gap-3 p-3"
      style={{ border: "var(--border-width-default) solid var(--color-border)", background: "var(--color-muted-soft)" }}
    >
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
              {move.start.points != null ? `Proj ${move.start.points.toFixed(1)}` : "No projection yet"}
            </span>
          </span>
          <span className="text-sm font-bold" style={{ color: "var(--color-text-primary)" }}>
            <span style={{ color: "var(--color-success)" }}>Start</span> {move.start.name || "Unknown player"}
          </span>
          <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
            {moveOverLine(move)}
          </span>
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
        The suggested lineup ranks by season-long value; gains are this week&apos;s projected points. FantasyDesk
        can&apos;t change your Sleeper lineup, so make any swap in Sleeper.
      </p>
    </section>
  );
}

import { GuillotineCard, useGuillotine } from "@/components/GuillotineCard";

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
      <main className="flex-1 flex flex-col gap-4 px-4 py-8 max-w-3xl w-full mx-auto">
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
      <main className="flex-1 flex flex-col gap-6 px-4 py-8 max-w-3xl w-full mx-auto">
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
    <main className="flex-1 flex flex-col gap-4 px-4 py-8 max-w-3xl w-full mx-auto">
      <MatchupHeader week={matchup.week} live={matchup.game_state === "live"} leagueName={leagueName} />
      <div className="flex flex-col gap-1">
        <BeginnerHelp term="matchupIntro" />
        <BeginnerHelp term="matchupWinProbability" />
      </div>
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
      <ValuesCredit />
    </main>
  );
}
