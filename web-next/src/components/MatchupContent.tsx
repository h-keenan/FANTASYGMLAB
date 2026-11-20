"use client";

import { FreshnessLabel } from "@/components/ui/FreshnessLabel";
import { PageTabBar } from "@/components/PageTabBar";
import { BEGINNER_HELP } from "@/lib/experienceCopy";
import { RangeCompare } from "@/components/RangeCompare";
import { TickNumber } from "@/components/TickNumber";
import { RANGE_CAPTION, leanLabel, rangeDisplayRows } from "@/lib/startSitRange";
import { useRouter } from "next/navigation";
import dynamic from "next/dynamic";
import { useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";

import type {
  MatchupPositionEdge,
  MatchupResponse,
  MatchupSide,
  MatchupSuggestedMove,
} from "@/lib/api";
import { Button } from "@/components/Button";
import { usePageHelp } from "@/components/PageHelpLines";
import { PageTitle } from "@/components/PageTitle";
import { EmptyState } from "@/components/EmptyState";
import { reloadPage } from "@/components/ErrorState";
import { PillRow } from "@/components/PillRow";
import { NextSteps } from "@/components/NextSteps";
import { PlannerBar, SwapSheet, useLineupPlanner } from "@/components/MatchupPlanner";
import { ComparisonHeader, SlotList } from "@/components/MatchupLineup";
import { feedKey, liveFeedStore } from "@/lib/liveFeed";
import { liveGamesFromStarters, mergeLivePlays } from "@/lib/matchupLive";
import { PlayerCard } from "@/components/PlayerCardKit";
import { playerCardFromStarter } from "@/lib/playerCard";
import { PositionBadge } from "@/components/PositionBadge";
import { StatStrip } from "@/components/StatStrip";
import { CompactModule } from "@/components/ui/CompactModule";
import { MatchupHeroCard, type MatchupLiveSections } from "@/components/ui/MatchupModule";
import { usePlayerQuickView } from "@/context/PlayerQuickViewContext";
import { bandColorVar } from "@/lib/verdictToneCss";
import { deltaBand } from "@/lib/verdictTone";
import { edgeChips, insightsParts, lineupParts, matchupCardModel, matchupSwingPlayers, movesParts, swingInputsFromMatchup, teamsValuesParts } from "@/lib/matchupModules";
import { TeamAvatar } from "@/components/TeamAvatar";
import { ToneBadge } from "@/components/ToneBadge";
import { freshnessLabel } from "@/lib/liveScores";
import { PageStatusLine } from "@/components/ui/PageStatusLine";
import { WeatherReasonChip } from "@/components/WeatherReasonChip";
import { ValuesCredit } from "@/components/ValuesCredit";
import {
  edgeExplanation,
  formatSeasonValue,
  formatSigned,
  hasKickedOff,
  lineupComparisonRows,
  lineupTotals,
  matchupActionLabel,
  matchupNextAction,
  matchupReasonMessage,
  matchupVerdict,
  moveOverLine,
  moveSlotLabel,
  recordLabel,
  winProbabilityNote,
  winProbabilityUnavailableMessage,
} from "@/lib/matchupPresentation";
import { compareLineupSlots, type SlotSortMode } from "@/lib/lineupSlots";
import { emptySlotsOf, plannerBase, plannerOpponentPlayers, slotIndexFor, winPercent } from "@/lib/matchupPlanner";
import { parseMatchupPlan } from "@/lib/todayView";

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

/** Margin colouring: green when up, muted otherwise (a down move gets an arrow, not red; verdictTone.ts). */
function deltaTone(value: number | null | undefined): "positive" | "neutral" {
  return deltaBand(value) === "good" ? "positive" : "neutral";
}

function signedTone(value: number | null | undefined): "positive" | "risk" | "neutral" {
  if (value == null || Math.abs(value) < 0.05) return "neutral";
  return value > 0 ? "positive" : "risk";
}

const ManagerProfileSheet = dynamic(() => import("@/components/ManagerProfileSheet").then((m) => m.ManagerProfileSheet), { ssr: false });

function MatchupHeader({
  week,
  live,
  leagueName,
  ageSeconds,
  onRefresh,
  refreshing,
}: {
  week: number | null;
  live: boolean;
  leagueName: string;
  ageSeconds?: number | null;
  onRefresh?: () => void;
  refreshing?: boolean;
}) {
  const pageHelp = usePageHelp([BEGINNER_HELP.matchupIntro, BEGINNER_HELP.matchupWinProbability]);
  // ONE compact line (PageStatusLine): "Week 10 . Live" left, "Updated 3m ago" + refresh icon right. The hero card does not repeat the week.
  return (
    <>
      <PageTitle page="Matchup" leagueName={leagueName} info={pageHelp} />
      <PageStatusLine
        context={
          <>
            {week != null ? <span>Week {week}</span> : null}
            {live ? (
              <span aria-label="Games in progress">
                <ToneBadge label="● Live" color="var(--color-success)" />
              </span>
            ) : null}
          </>
        }
        freshness={onRefresh ? (ageSeconds != null ? freshnessLabel(ageSeconds) : "Live scores") : null}
        onRefresh={onRefresh}
        refreshing={refreshing}
        testId="matchup-freshness"
      />
    </>
  );
}

function ScoreSide({
  side,
  mine,
  score,
  projected,
  kickedOff,
  onOpenTeam,
}: {
  side: MatchupSide;
  mine: boolean;
  /** Opens the team sheet (the opponent's name is the tap target). */
  onOpenTeam?: () => void;
  score: number | null;
  projected: number | null;
  kickedOff: boolean;
}) {
  // Before any game kicks off, Sleeper's 0.0 isn't a score yet, so the
  // projection leads; once games start the real score leads.
  const live = kickedOff && score != null;
  const headline = live ? score : projected;
  const caption = live ? (projected != null ? <TickNumber value={projected} format={(n) => `Proj ${n.toFixed(1)}`} /> : null) : "Projected";
  return (
    <div className="flex-1 flex flex-col items-center text-center gap-1 min-w-0">
      <TeamAvatar
        avatarUrl={side.avatar_url}
        name={side.team_name}
        size={56}
        ringColor={mine ? "var(--color-accent)" : "var(--color-border-strong)"}
      />
      {onOpenTeam ? (
        <button type="button" onClick={onOpenTeam} className="text-sm font-bold break-words w-full underline decoration-dotted underline-offset-2" style={{ color: "var(--color-text-primary)", minHeight: 44 }} aria-label={`Open ${side.team_name} team sheet`}>
          {side.team_name}
        </button>
      ) : (
        <span className="text-sm font-bold break-words w-full" style={{ color: "var(--color-text-primary)" }}>
          {side.team_name}
        </span>
      )}
      <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
        {recordLabel(side)}
      </span>
      <TickNumber value={headline} style={{ font: "var(--type-primary-metric)", color: "var(--color-text-primary)" }} />
      {caption ? (
        <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          {caption}
        </span>
      ) : null}
    </div>
  );
}

function scoreboardFacts(matchup: MatchupResponse) {
  const odds = matchup.win_probability;
  const hasOdds = odds?.available === true && odds.probability != null;
  const myPct = hasOdds ? Math.round(odds!.probability! * 100) : null;
  const myProjected = hasOdds ? (odds!.my_projected_total ?? null) : null;
  const opponentProjected = hasOdds ? (odds!.opponent_projected_total ?? null) : null;
  const projectedMargin = myProjected != null && opponentProjected != null ? myProjected - opponentProjected : null;
  return { hasOdds, myPct, myProjected, opponentProjected, projectedMargin };
}

/**
 * Hero (V1): week + live state, win chance, both scores, the win bar, projection / players left, and the swing player on
 * each side (widest projection range still to play) with their avatars. "Open lineup" jumps to the lineup comparison.
 */
const EMPTY_FEED: ReturnType<typeof liveFeedStore.events> = [];

function MatchupHero({ matchup, leagueId, ageSeconds }: { matchup: MatchupResponse; leagueId?: string | null; ageSeconds?: number | null }) {
  const mine = matchup.my_team!;
  const opponent = matchup.opponent!;
  const { openPlayer } = usePlayerQuickView();
  const { myPct, myProjected, opponentProjected } = scoreboardFacts(matchup);
  const { inputs: swingInputs, playersLeft } = swingInputsFromMatchup(mine, opponent);
  const model = matchupCardModel({
    week: matchup.week,
    live: matchup.game_state === "live",
    final: matchup.game_state === "final",
    myName: "You",
    opponentName: opponent.team_name,
    myScore: mine.has_live_data ? mine.real_points : null,
    opponentScore: opponent.has_live_data ? opponent.real_points : null,
    myProjected,
    opponentProjected,
    winPercent: myPct,
    kickedOff: hasKickedOff(matchup),
    playersLeft: hasKickedOff(matchup) ? playersLeft : null,
    swing: matchupSwingPlayers(swingInputs, opponent.team_name),
    omitWeek: true,
  });
  const feedEvents = useSyncExternalStore(
    liveFeedStore.subscribe,
    () => (leagueId ? liveFeedStore.events(feedKey(leagueId, matchup.week)) : EMPTY_FEED),
    () => EMPTY_FEED,
  );
  const live = matchup.game_state === "live";
  const kicked = hasKickedOff(matchup);
  const liveSections: MatchupLiveSections | undefined = kicked
    ? {
        live,
        games: liveGamesFromStarters([...(mine.real_starters ?? []), ...(opponent.real_starters ?? [])]),
        plays: live || matchup.big_plays?.length ? mergeLivePlays(matchup.big_plays, feedEvents) : [],
        ageSeconds: ageSeconds ?? null,
        projectedLine: model.detail,
        projected: myProjected != null && opponentProjected != null ? { mine: myProjected.toFixed(1), opponent: opponentProjected.toFixed(1) } : null,
      }
    : undefined;
  return (
    <>
      <MatchupHeroCard
        model={model}
        liveSections={liveSections}
        onOpenPlayer={(p) => p.playerId && openPlayer({ player_id: p.playerId, name: p.name, position: p.position, team: p.team, tier: p.tier })}
        action={
          <Button
            fullWidth
            onClick={() => document.querySelector('[data-testid="matchup-lineup"]')?.scrollIntoView({ behavior: "smooth", block: "start" })}
            data-testid="matchup-open-lineup"
          >
            Open lineup
          </Button>
        }
      />
      {myPct == null ? (
        <p className="m-0 text-xs" style={{ color: "var(--color-text-muted)" }}>
          {winProbabilityUnavailableMessage(matchup)}
        </p>
      ) : winProbabilityNote(matchup) ? (
        <p className="m-0 text-xs" style={{ color: "var(--color-text-muted)" }}>
          {winProbabilityNote(matchup)}
        </p>
      ) : null}
    </>
  );
}

/** Teams, both scores, the win-probability bar and the value tiles: one compact module under the Hero. */
function TeamsValues({ matchup, leagueId, leagueName = "" }: { matchup: MatchupResponse; leagueId?: string; leagueName?: string }) {
  const [sheetOpen, setSheetOpen] = useState(false);
  const mine = matchup.my_team!;
  const opponent = matchup.opponent!;
  const comparison = matchup.comparison!;
  const { myProjected, opponentProjected, projectedMargin } = scoreboardFacts(matchup);
  const kickedOff = hasKickedOff(matchup);
  const valueMargin =
    comparison.margin === 0 ? "0" : `${comparison.margin > 0 ? "+" : "-"}${formatSeasonValue(Math.abs(comparison.margin))}`;

  return (
    <CompactModule
      id="matchup.teams"
      title="Teams & values"
      testId="matchup-teams"
      parts={teamsValuesParts({
        myValue: formatSeasonValue(comparison.my_season_value),
        opponentValue: formatSeasonValue(comparison.opponent_season_value),
        valueMargin,
        edge: comparison.edge,
        projectedMargin,
      })}
    >
      <div className="flex flex-col gap-4" aria-label="Scoreboard">
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
            onOpenTeam={leagueId && opponent.roster_id ? () => setSheetOpen(true) : undefined}
          />
          {sheetOpen && leagueId ? (
            <ManagerProfileSheet
              leagueId={leagueId}
              leagueName={leagueName}
              rosterId={opponent.roster_id}
              teamName={opponent.team_name}
              ownerName={opponent.owner_name}
              avatarUrl={opponent.avatar_url}
              onClose={() => setSheetOpen(false)}
            />
          ) : null}
        </div>

        {/* Win chance, its bar and its label live in the hero (one owner per fact). */}

        {/* Symmetric: each team's season value on the outside, the two matchup-level margins inside. */}
        <StatStrip
          columns={4}
          items={[
            { glyph: "starter", label: "Your value", value: formatSeasonValue(comparison.my_season_value) },
            {
              glyph: "power",
              label: "Proj margin",
              value: projectedMargin != null ? formatSigned(projectedMargin) : "—",
              tone: deltaTone(projectedMargin),
            },
            { glyph: "starter", label: "Their value", value: formatSeasonValue(comparison.opponent_season_value) },
            {
              glyph: "franchise",
              label: "Value margin",
              value: valueMargin,
              tone: comparison.edge === "you" ? "positive" : "neutral",
            },
          ]}
        />
      </div>
    </CompactModule>
  );
}

function EdgeArrow({ edge }: { edge: number }) {
  const tone = signedTone(edge);
  const color = tone === "positive" ? bandColorVar("good") : "var(--color-text-muted)";
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

/** Position edges as chips right beside the sentence they explain (biggest swing first). */
function EdgeChips({ edges }: { edges: MatchupPositionEdge[] }) {
  return (
    <ul className="flex flex-wrap gap-1.5" aria-label="Position edges">
      {edgeChips(edges).map((chip) => {
        const color = chip.tone === "success" ? bandColorVar("good") : "var(--color-text-muted)";
        const edge = edges.find((e) => e.position === chip.position)!;
        return (
          <li
            key={chip.position}
            className="inline-flex items-center gap-1.5 px-2 py-1"
            style={{ border: "var(--border-width-default) solid var(--color-border)", borderRadius: "var(--radius-pill)" }}
          >
            <EdgeArrow edge={edge.edge} />
            <PositionBadge position={chip.position} />
            <span className="text-sm font-extrabold tabular-nums" style={{ color }}>
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
    <CompactModule
      id="matchup.insights"
      title="Matchup Insights"
      testId="matchup-insights"
      defaultOpen
      tone="accent"
      parts={insightsParts(verdict.headline, edges)}
    >
      <div className="flex flex-col gap-2.5">
        {explanation ? (
          <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
            {explanation}
          </p>
        ) : (
          <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
            No position projections yet to compare.
          </p>
        )}
        {edges.length ? <EdgeChips edges={edges} /> : null}
        <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          {basis}
        </p>
      </div>
    </CompactModule>
  );
}

type LineupView = "suggested" | "actual";

function LineupComparison({
  matchup,
  view,
  onViewChange,
  leagueId,
  planner,
  ageSeconds,
}: {
  matchup: MatchupResponse;
  view: LineupView;
  onViewChange: (view: LineupView) => void;
  leagueId?: string;
  planner?: ReturnType<typeof useLineupPlanner>;
  ageSeconds?: number | null;
}) {
  const mine = matchup.my_team!;
  const opponent = matchup.opponent!;
  const bestBall = matchup.best_ball === true;
  const actual = bestBall || view === "actual";
  const plan = planner?.plan ?? null;
  const canPlan = Boolean(planner && leagueId && !bestBall && plannerBase(matchup, view));
  const [helpOpen, setHelpOpen] = useState(false);
  const rows = useMemo(() => (plan
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
    : lineupComparisonRows(mine.starters, opponent.starters)), [plan, actual, mine, opponent, matchup]);
  const slots = useMemo(() => compareLineupSlots(rows), [rows]);
  const [sort, setSort] = useState<SlotSortMode>("lineup");
  const caption = plan
    ? "Tap one of your players to see who could take the slot. A planner only: make the final change in Sleeper."
    : actual
    ? "Lineups as set in Sleeper."
    : "Our best lineup for each team, run the same way for both sides. A planner only: set your lineup in Sleeper.";

  const totals = lineupTotals(rows);
  return (
    <CompactModule
      id="matchup.lineup"
      title="Lineup Comparison"
      testId="matchup-lineup"
      defaultOpen
      parts={lineupParts({
        view: actual ? "actual" : "suggested",
        mineTotal: rows.length ? totals.mine : null,
        opponentTotal: rows.length ? totals.opponent : null,
        slotCount: rows.length,
        bestBall,
      })}
    >
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-end gap-2">
        <button
          type="button"
          aria-label={helpOpen ? "Hide explanation" : "How this works"}
          aria-expanded={helpOpen}
          onClick={() => setHelpOpen((v) => !v)}
          className="inline-flex items-center justify-center shrink-0"
          style={{ width: "var(--touch-target-min)", height: "var(--touch-target-min)" }}
        >
          <span
            className="inline-flex items-center justify-center font-bold text-xs"
            style={{ width: 22, height: 22, borderRadius: 9999, border: "var(--border-width-default) solid var(--color-border)", color: "var(--color-accent)", lineHeight: 1 }}
          >
            ?
          </span>
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
        <div className="flex flex-wrap items-center justify-between gap-2">
          <PillRow
            options={[
              { label: "Suggested", value: "suggested", glyph: "suggested" },
              { label: "Actual", value: "actual", glyph: "actual" },
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
        <>
          <ComparisonHeader
            mine={mine}
            opponent={opponent}
            slots={slots}
            odds={matchup.win_probability}
            ageSeconds={ageSeconds}
            live={matchup.game_state === "live"}
            sort={sort}
            onSort={setSort}
          />
          <SlotList
            slots={slots}
            sort={sort}
            planEditIndex={
              plan
                ? (slot) => {
                    const emptyOrdinal =
                      slot.row.mine === "empty"
                        ? rows.slice(0, slot.index).filter((r) => r.slot === slot.slot && r.mine === "empty").length
                        : 0;
                    const editIndex = slotIndexFor(plan.slots, slot.row.mine, slot.slot, emptyOrdinal);
                    return editIndex >= 0 ? () => void planner!.openSlot(editIndex) : undefined;
                  }
                : undefined
            }
          />
        </>
      )}
    </div>
    </CompactModule>
  );
}

function MoveCard({ move, slotLabel }: { move: MatchupSuggestedMove; slotLabel: string }) {
  const tone = signedTone(move.gain);
  const gainColor = tone === "positive" ? bandColorVar("good") : "var(--color-text-muted)";
  return (
    <li
      className="flex flex-col gap-2 p-3"
      style={{ border: "var(--border-width-default) solid var(--color-border)", background: "var(--color-muted-soft)" }}
    >
      <div className="flex items-center gap-3">
      <div className="flex-1 flex flex-col gap-1.5 min-w-0">
        <span className="flex items-center gap-2">
          <PositionBadge position={move.slot} label={slotLabel} />
          <span className="text-[11px] font-extrabold uppercase" style={{ color: "var(--color-success)", letterSpacing: "var(--letter-spacing-badge)" }}>
            Start
          </span>
        </span>
        <PlayerCard
          variant="compact"
          model={playerCardFromStarter({
            player_id: move.start.player_id,
            name: move.start.name,
            position: move.start.position,
            team: move.start.team,
            tier: move.start.tier,
            injury_label: move.start.injury_label,
            projection:
              move.start.points != null
                ? { status: "ok", point_estimate: move.start.points }
                : move.start.projection_status
                  ? { status: move.start.projection_status, point_estimate: null }
                  : null,
          })}
          identity={{
            player_id: move.start.player_id ?? "",
            name: move.start.name,
            position: move.start.position,
            team: move.start.team,
            tier: move.start.tier,
            sourceLabel: "Matchup",
          }}
          stats={[{ label: "Proj", value: move.start.points != null ? move.start.points.toFixed(1) : "—" }]}
        />
        <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          {move.start.points == null ? `${move.start_note || "No projection yet"}. ` : ""}
          {moveOverLine(move)}
        </span>
        <WeatherReasonChip notes={move.weather_notes?.filter((note) => note.applied)} />
      </div>
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
    <CompactModule
      id="matchup.moves"
      title="Suggested Moves"
      testId="matchup-moves"
      parts={movesParts(moves ? moves.map((m) => ({ startName: m.start.name ?? "player", gain: m.gain ?? null })) : null)}
    >
      <div className="flex flex-col gap-3">
        {moves !== null && hiddenCount > 0 ? (
          <button
            type="button"
            onClick={() => setExpanded((value) => !value)}
            aria-expanded={expanded}
            className="self-start text-xs font-bold"
            style={{ color: "var(--color-accent)" }}
          >
            {expanded ? "Show fewer" : `View all (${moves.length})`}
          </button>
        ) : null}
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
      </div>
    </CompactModule>
  );
}

import { GuillotineCard, useGuillotine } from "@/components/GuillotineCard";

export function MatchupContent({
  leagueName,
  matchup,
  leagueId,
  lens = "Dynasty",
  ageSeconds,
  refreshing = false,
  onRefresh,
}: {
  leagueName: string;
  matchup: MatchupResponse;
  leagueId?: string;
  lens?: string;
  /** Current age of the live scores (server as_of + time since received); omit to hide the indicator. */
  ageSeconds?: number | null;
  refreshing?: boolean;
  onRefresh?: () => void;
}) {
  const router = useRouter();
  const guillotineData = useGuillotine(leagueId, lens);
  const guillotine = guillotineData?.is_guillotine ? guillotineData : null;
  const ready = matchup.ok && matchup.my_team && matchup.opponent && matchup.comparison;
  const defaultView: LineupView = matchup.my_team?.has_live_data ? "actual" : "suggested";
  // "Fix all" (?plan=all) opens on the suggested lineup; a single swap opens on the real one (defaultView).
  const [view, setView] = useState<LineupView>(() =>
    typeof window !== "undefined" && new URLSearchParams(window.location.search).get("plan") === "all" ? "suggested" : defaultView,
  );
  const planner = useLineupPlanner(leagueId ?? "", lens, matchup);
  const edited = planner.plan?.result;
  // Today's "Swap" / "Fix all" open this page with the planner already on that move (?plan=swap&out=&in= / ?plan=all).
  const autoPlanned = useRef(false);
  useEffect(() => {
    if (autoPlanned.current || !ready || guillotine) return;
    autoPlanned.current = true;
    const params = new URLSearchParams(window.location.search);
    const request = parseMatchupPlan({ plan: params.get("plan"), out: params.get("out"), in: params.get("in") });
    if (!request) return;
    const source = request.kind === "swap" && matchup.my_team?.has_live_data ? "actual" : "suggested";
    planner.start(source, request.kind === "swap" && source === "actual" ? { out: request.out, in: request.in } : undefined);
    requestAnimationFrame(() => document.querySelector('[data-testid="matchup-lineup"]')?.scrollIntoView?.({ behavior: "smooth", block: "start" }));
  }, [ready, guillotine, matchup.my_team?.has_live_data, planner]);
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
      <main className="page-shell">
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
      <main className="page-shell">
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
    <main className="page-shell page-shell-wide">
      {leagueId ? <PageTabBar family="team" active="matchup" leagueId={leagueId} leagueName={leagueName} /> : null}
      <MatchupHeader week={matchup.week} live={matchup.game_state === "live"} leagueName={leagueName} ageSeconds={ageSeconds} onRefresh={onRefresh} refreshing={refreshing} />
      {matchup.sleeper_data_as_of ? <FreshnessLabel datasets={[]} report={null} leagueAsOf={matchup.sleeper_data_as_of} className="block text-xs" /> : null}
      <MatchupHero matchup={shown} leagueId={leagueId} ageSeconds={ageSeconds} />
      {matchup.unmapped_players && matchup.unmapped_players.length > 0 ? (
        <p className="m-0 text-xs" style={{ color: "var(--color-text-muted)" }} data-testid="unmapped-starters">
          Not matched to a FantasyDesk player, so left out of the lineups and win odds:{" "}
          {matchup.unmapped_players.map((p) => `${p.name} (${p.fantasy_team})`).join(", ")}.
        </p>
      ) : null}
      <div className="matchup-grid" data-testid="matchup-grid">
      <div className="matchup-col-main lg:col-start-1">
        <MatchupInsights matchup={shown} />
      </div>
      <div className="matchup-col-lineup flex flex-col gap-[var(--page-gap)] min-w-0 lg:col-start-2 lg:row-start-1 lg:row-span-3">
      <LineupComparison
        matchup={matchup}
        view={view}
        onViewChange={setView}
        leagueId={leagueId}
        planner={leagueId ? planner : undefined}
        ageSeconds={ageSeconds}
      />
      {planner.sheet && planner.plan ? (
        <SwapSheet
          sheet={planner.sheet}
          slot={planner.plan.slots[planner.sheet.index]?.slot ?? ""}
          onPick={planner.pick}
          onClose={planner.closeSheet}
        />
      ) : null}
      </div>
      <div className="lg:col-start-1"><TeamsValues matchup={shown} leagueId={leagueId} leagueName={leagueName} /></div>
      <div className="lg:col-start-1">
      {matchup.best_ball ? (
        // Best ball: Sleeper sets both lineups from the highest weekly
        // scorers, so there is no suggested lineup or start/sit call.
        <p className="glass-surface text-sm p-4" style={{ color: "var(--color-text-secondary)" }}>
          {matchup.lineup_advice_message}
        </p>
      ) : (
        <SuggestedMoves matchup={matchup} />
      )}
      </div>
      </div>
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
