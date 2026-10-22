"use client";

import { EmptyState } from "@/components/EmptyState";
import { PlayerIdentity } from "@/components/PlayerRow";
import { ValueStat } from "@/components/ValueStat";
import { SectionHeading } from "@/components/SectionHeading";
import { useMemo, useState } from "react";

import type {
  LiveDraftDiscoveryResponse,
  LiveDraftPickRow,
  LiveDraftRankingRow,
  LiveDraftRecommendation,
  LiveDraftStateResponse,
  LiveDraftTeamRow,
} from "@/lib/api";
import { OvrGauge } from "@/components/OvrGauge";
import { PlayerIdentityTrigger } from "@/components/PlayerIdentityTrigger";
import { PositionBadge } from "@/components/PositionBadge";
import { PremiumUpsellCard } from "@/components/PremiumUpsellCard";
import { LiveDraftTradeEvaluator } from "@/components/LiveDraftTradeEvaluator";
import {
  filterLiveDraftRankings,
  formatLiveDraftScore,
  liveDraftRankFilterOptions,
  movementGlyph,
  type LiveDraftRankFilter,
} from "@/lib/liveDraftPresentation";
import { ValuesCredit } from "@/components/ValuesCredit";

/**
 * Live Draft (Revision 21) — the last page on the original migration punch
 * list. Unlike every earlier revision, there's no mobile reference screen:
 * this is a genuine feature-parity gap (tonight's nav audit flagged Live
 * Draft as "exists only on web, no mobile screen at all"), so this ports
 * modules/live_draft_ui.py's render_live_draft_page directly — the
 * read-only Sleeper draft-room assistant: on-the-clock status, Best
 * Available/Best Fit/Safe/Upside/Position Need recommendations, the full
 * available-player board reranked live, a live roster-strength team board,
 * and recent pick history. Polls GET .../live-draft/{draftId} every 12s
 * (see app/live-draft/[leagueId]/page.tsx) instead of Streamlit's
 * st.fragment(run_every=...) full-page rerun — a cleaner fit for a
 * single-page app than the thing it's replacing.
 *
 * The hypothetical mid-draft Trade Evaluator (modules/
 * live_draft_trade_evaluator.py's pick/player multiselect form) now ports
 * here too, as its own LiveDraftTradeEvaluator component below. The
 * per-player score-breakdown lookup (modules/live_draft_ui.py's "Score
 * breakdown" expander) is ported too, as a tap-to-reveal on each
 * RankingRowView's score — coridian_: "another redirect to the classic
 * website to view the full live draft" was this page's last deep link out
 * to the classic Streamlit page; there's no remaining reason to leave it.
 */

function RecommendationCard({ rec, primary }: { rec: LiveDraftRecommendation; primary: boolean }) {
  return (
    <div
      className="flex flex-col gap-2 p-3"
      style={{
        background: primary ? "var(--color-surface-secondary)" : "var(--color-surface-primary)",
        border: `var(--border-width-default) solid ${primary ? "var(--color-accent)" : "var(--color-border)"}`,
      }}
    >
      <div className="flex items-center justify-between gap-3">
        <PlayerIdentityTrigger identity={{ ...rec, sourceLabel: "Live Draft" }} className="flex items-center gap-3 min-w-0">
          <PositionBadge position={rec.position} />
          <div className="flex flex-col min-w-0">
            <span className="text-sm font-bold truncate" style={{ color: "var(--color-text-primary)" }}>
              {rec.name || `Player ${rec.player_id}`}
            </span>
            <span className="text-xs truncate" style={{ color: "var(--color-text-muted)" }}>
              {rec.team || "—"} · {rec.tier || "Board Value"}
            </span>
          </div>
        </PlayerIdentityTrigger>
        <div className="flex items-center gap-2 shrink-0">
          <span className="text-sm font-extrabold" style={{ color: "var(--color-accent)" }}>
            {formatLiveDraftScore(rec.league_adjusted_draft_score)}
          </span>
          <OvrGauge rating={rec.overall_rating} size="sm" />
        </div>
      </div>
      <div className="flex flex-wrap gap-1.5">
        <span
          className="px-1.5 py-0.5 text-xs font-bold"
          style={{ background: "var(--color-information-soft)", color: "var(--color-text-secondary)" }}
        >
          {rec.recommendation_role}
        </span>
        {!primary ? (
          <span
            className="px-1.5 py-0.5 text-xs font-bold"
            style={{ background: "var(--color-surface-muted)", color: "var(--color-text-secondary)" }}
          >
            {rec.confidence} confidence
          </span>
        ) : null}
        {rec.position_need_impact ? (
          <span
            className="px-1.5 py-0.5 text-xs font-bold"
            style={{ background: "var(--color-success-soft)", color: "var(--color-success)" }}
          >
            {rec.position_need_impact}
          </span>
        ) : null}
      </div>
      {primary ? (
        <div className="flex flex-col gap-1 text-xs" style={{ color: "var(--color-text-secondary)" }}>
          <p>{rec.recommendation_reason}</p>
          <div className="flex flex-wrap gap-x-4 gap-y-1" style={{ color: "var(--color-text-muted)" }}>
            <span>Roster impact: {rec.immediate_roster_impact}</span>
            <span>
              Value vs ADP: {rec.adp_delta !== null ? `${rec.adp_delta > 0 ? "+" : ""}${rec.adp_delta}` : "unavailable"}
            </span>
            <span>Confidence: {rec.confidence}</span>
          </div>
        </div>
      ) : null}
    </div>
  );
}

// Label/column order mirrors modules/live_draft_ui.py's own "Score
// breakdown" expander exactly (Base/Format/Scarcity/Fit/Age-Strategy/
// Availability), so this reads as the same feature, not a new one.
const SCORE_BREAKDOWN_FIELDS: { key: keyof LiveDraftRankingRow; label: string }[] = [
  { key: "base_value", label: "Base" },
  { key: "format_adjustment", label: "Format" },
  { key: "scarcity_score", label: "Scarcity" },
  { key: "roster_fit_score", label: "Fit" },
  { key: "age_strategy_adjustment", label: "Age/Strategy" },
  { key: "availability_adjustment", label: "Availability" },
];

function RankingRowView({ row, leagueId, leagueName }: { row: LiveDraftRankingRow; leagueId: string; leagueName: string }) {
  const movement = movementGlyph(row.movement);
  const [showBreakdown, setShowBreakdown] = useState(false);
  return (
    <div className="py-2" style={{ borderBottom: "var(--border-width-default) solid var(--color-border)" }}>
      <div className="flex items-center justify-between gap-3">
        <PlayerIdentity
          identity={{ ...row, leagueId, leagueName, sourceLabel: "Live Draft" }}
          playerId={row.player_id}
          name={row.name || `Player ${row.player_id}`}
          position={row.position}
          tier={row.tier}
          leading={
            <span className="text-xs font-bold w-8 shrink-0" style={{ color: "var(--color-text-muted)" }}>
              #{row.overall_rank ?? "—"}
            </span>
          }
        >
          {row.team || "—"}
          {row.position && row.position_rank ? ` · ${row.position}${row.position_rank}` : ""}
          {row.recommendation_label ? ` · ${row.recommendation_label}` : ""}
        </PlayerIdentity>
        <div className="flex items-center gap-2 shrink-0">
          <span
            className="text-xs font-bold w-10 text-right"
            style={{ color: row.movement >= 2 ? "var(--color-success)" : row.movement <= -2 ? "var(--color-danger)" : "var(--color-text-muted)" }}
          >
            {movement}
          </span>
          {/* coridian_: "another redirect to the classic website to view
              the full live draft" — this tap-to-reveal breakdown is what
              that link used to send people to a separate page for. */}
          <ValueStat value="">
            <button
              type="button"
              onClick={() => setShowBreakdown((value) => !value)}
              aria-expanded={showBreakdown}
              aria-label="Score breakdown"
              className="text-sm font-extrabold underline decoration-dotted"
              style={{ color: "var(--color-accent)" }}
            >
              {formatLiveDraftScore(row.league_adjusted_draft_score)}
            </button>
          </ValueStat>
          <OvrGauge rating={row.overall_rating} size="sm" />
          <a
            href={`/player-compare/${encodeURIComponent(leagueId)}?a=${encodeURIComponent(row.player_id)}&name=${encodeURIComponent(leagueName)}`}
            className="px-2 py-1 text-xs font-bold"
            style={{ color: "var(--color-text-secondary)", border: "var(--border-width-default) solid var(--color-border)" }}
          >
            Compare
          </a>
        </div>
      </div>
      {showBreakdown ? (
        <div className="flex flex-wrap gap-x-3 gap-y-1 mt-2 pl-11 text-xs" style={{ color: "var(--color-text-secondary)" }}>
          {SCORE_BREAKDOWN_FIELDS.map(({ key, label }) => (
            <span key={key}>
              {label} {formatLiveDraftScore(row[key] as number | null)}
            </span>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function TeamRankingRowView({ row }: { row: LiveDraftTeamRow }) {
  const movement = movementGlyph(row.movement);
  return (
    <div
      className="flex items-center justify-between gap-3 py-2"
      style={{ borderBottom: "var(--border-width-default) solid var(--color-border)" }}
    >
      <div className="flex items-center gap-3 min-w-0">
        <span className="text-xs font-bold w-8 shrink-0" style={{ color: "var(--color-text-muted)" }}>
          #{row.team_rank}
        </span>
        <div className="flex flex-col min-w-0">
          <span className="text-sm font-bold truncate" style={{ color: row.is_mine ? "var(--color-accent)" : "var(--color-text-primary)" }}>
            {row.team_name}
            {row.is_mine ? " (You)" : ""}
          </span>
          <span className="text-xs truncate" style={{ color: "var(--color-text-muted)" }}>
            {row.trend_label ? `${row.trend_label} · ` : ""}
            {row.positions || "No players yet"}
          </span>
        </div>
      </div>
      <div className="flex items-center gap-3 shrink-0 text-right">
        <span
          className="text-xs font-bold w-10"
          style={{ color: row.movement >= 2 ? "var(--color-success)" : row.movement <= -2 ? "var(--color-danger)" : "var(--color-text-muted)" }}
        >
          {movement}
        </span>
        <div className="flex flex-col">
          <span className="text-sm font-extrabold" style={{ color: "var(--color-accent)" }}>
            {Math.round(row.live_team_score)}
          </span>
          <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
            {row.pick_count} picks
          </span>
        </div>
      </div>
    </div>
  );
}

function PickRowView({ row }: { row: LiveDraftPickRow }) {
  return (
    <div
      className="flex items-center justify-between gap-3 py-1.5"
      style={{
        borderBottom: "var(--border-width-default) solid var(--color-border)",
        background: row.is_mine ? "var(--color-accent-soft)" : "transparent",
      }}
    >
      <PlayerIdentityTrigger
        identity={{ player_id: row.player_id, name: row.player_name, position: row.position, team: row.team, sourceLabel: "Live Draft" }}
        className="flex items-center gap-2 min-w-0"
      >
        <span className="text-xs font-bold w-10 shrink-0" style={{ color: "var(--color-text-muted)" }}>
          #{row.pick_no}
        </span>
        <PositionBadge position={row.position} />
        <span className="text-sm font-bold truncate" style={{ color: "var(--color-text-primary)" }}>
          {row.player_name}
        </span>
        <span className="text-xs truncate" style={{ color: "var(--color-text-muted)" }}>
          {row.team}
        </span>
      </PlayerIdentityTrigger>
      <span className="text-xs shrink-0" style={{ color: "var(--color-text-muted)" }}>
        {row.fantasy_team}
      </span>
    </div>
  );
}

function RankingsBoard({
  rows,
  leagueId,
  leagueName,
}: {
  rows: LiveDraftRankingRow[];
  leagueId: string;
  leagueName: string;
}) {
  const [filter, setFilter] = useState<LiveDraftRankFilter>("Overall");
  const options = useMemo(() => liveDraftRankFilterOptions(rows), [rows]);
  const filtered = useMemo(() => filterLiveDraftRankings(rows, filter), [rows, filter]);
  const visible = filtered.slice(0, 60);

  return (
    <section className="flex flex-col gap-3" aria-labelledby="live-draft-rankings-heading">
      <div className="flex items-center justify-between gap-3">
        <SectionHeading id="live-draft-rankings-heading">
          Available Player Rankings
        </SectionHeading>
        <select
          value={options.includes(filter) ? filter : "Overall"}
          onChange={(event) => setFilter(event.target.value as LiveDraftRankFilter)}
          className="filter-select px-3 py-2 text-sm"
        >
          {options.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      </div>
      <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
        Every undrafted player, reranked for this league and your roster. Tap Compare for the full breakdown.
      </p>
      {visible.length === 0 ? (
        <EmptyState title="No available players are loaded yet." />
      ) : (
        <div className="flex flex-col">
          {visible.map((row) => (
            <RankingRowView key={row.player_id} row={row} leagueId={leagueId} leagueName={leagueName} />
          ))}
        </div>
      )}
      {filtered.length > visible.length ? (
        <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          Showing the top {visible.length} of {filtered.length} ranked players.
        </p>
      ) : null}
    </section>
  );
}

export function LiveDraftContent({
  leagueId,
  leagueName,
  discovery,
  selectedDraftId,
  onSelectDraft,
  state,
  stateError,
  onRefresh,
  lens = "Dynasty",
}: {
  leagueId: string;
  leagueName: string;
  discovery: LiveDraftDiscoveryResponse;
  selectedDraftId: string;
  onSelectDraft: (draftId: string) => void;
  state: LiveDraftStateResponse | null;
  stateError: string | null;
  onRefresh: () => void;
  lens?: string;
}) {
  const liveOrPaused = discovery.drafts.filter((draft) => draft.status === "drafting" || draft.status === "paused");
  const hasCompleted = discovery.drafts.some((draft) => draft.status === "complete");

  // coridian_, 2026-10-18: "Live draft needs to be locked." A real
  // top-level return, not nested inside this component's own <main> below
  // — PremiumUpsellCard renders its own full <main>, and nesting one
  // inside another is invalid HTML (and would double up the page padding/
  // width constraints). Takes priority over the "no live draft found"
  // messaging further down — a Free caller sees the upgrade prompt
  // regardless of whether a draft actually exists right now.
  if (!discovery.is_premium) {
    return (
      <PremiumUpsellCard
        kicker="Live Draft"
        upsell={discovery.upsell}
        fallbackTitle="Draft with real-time recommendations"
        fallbackBody="Live Draft is a Premium feature — Best Available/Best Fit picks, a live roster-strength board, and positional-run alerts while your draft is actually happening. Upgrade to Premium to unlock it."
      />
    );
  }

  return (
    <main className="flex-1 flex flex-col gap-8 px-4 py-8 max-w-3xl w-full mx-auto">
      <header className="flex flex-col gap-1">
        <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          Live Draft
        </span>
        <h1 style={{ font: "var(--font-page-title)" }}>{leagueName}</h1>
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
          Read-only Sleeper draft-room assistant. Picks and recommendations update automatically — nothing is
          submitted to Sleeper.
        </p>
      </header>

      {/* coridian_, 2026-10-19: "at least put a coming soon tag on the live
          draft section for now" — this page is real and functional, but
          completely untested end-to-end against a live draft (see
          docs/roadmap.md's open-initiatives entry). Not gated/disabled,
          just honestly labeled while that testing pass is still pending. */}
      <div
        className="glass-input flex items-center gap-2 px-3 py-2 text-xs"
        style={{ borderLeft: "var(--border-width-semantic) solid var(--color-warning)", color: "var(--color-text-secondary)" }}
      >
        <span className="font-bold uppercase" style={{ color: "var(--color-warning)", letterSpacing: "var(--letter-spacing-badge)" }}>
          Coming soon
        </span>
        <span>This page is still being tested end-to-end against a real live draft — treat recommendations as a preview.</span>
      </div>

      {liveOrPaused.length === 0 ? (
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
          {discovery.drafts.length === 0
            ? "No Sleeper drafts were found for this league yet."
            : hasCompleted
              ? "The latest Sleeper draft has ended. Live Draft activates again when a draft is in progress or paused."
              : "No live Sleeper draft is active. This workspace appears only while a draft is in progress or paused."}
        </p>
      ) : (
        <>
          {liveOrPaused.length > 1 ? (
            <select
              value={selectedDraftId}
              onChange={(event) => onSelectDraft(event.target.value)}
              className="filter-select px-3 py-2 text-sm self-start"
            >
              {liveOrPaused.map((draft) => (
                <option key={draft.draft_id} value={draft.draft_id}>
                  {draft.name || `Draft ${draft.draft_id}`} · {draft.season} · {draft.status}
                </option>
              ))}
            </select>
          ) : null}

          {stateError ? (
            <p role="alert" style={{ color: "var(--color-danger)" }}>
              {stateError}
            </p>
          ) : null}

          {!state ? (
            <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
              Loading the live draft board…
            </p>
          ) : (
            <>
              <div className="flex flex-wrap gap-2">
                {[
                  state.status,
                  `${state.picks_made} picks logged`,
                  `${state.rounds} rounds`,
                  `${state.teams} teams`,
                  state.league_settings.scoring_format,
                  state.league_settings.qb_format,
                  state.league_settings.league_format,
                  state.score_label,
                ].map((chip, index) => (
                  <span
                    key={index}
                    className="px-2 py-1 text-xs font-bold uppercase"
                    style={{
                      background: "var(--color-surface-muted)",
                      color: "var(--color-text-secondary)",
                      letterSpacing: "0.03em",
                    }}
                  >
                    {chip}
                  </span>
                ))}
              </div>

              {state.pick_data_stale ? (
                <p className="text-xs" style={{ color: "var(--color-warning)" }}>
                  Sleeper pick data is temporarily unavailable. Showing the last valid read-only board.
                </p>
              ) : null}
              {state.status === "complete" ? (
                <p className="text-sm font-bold" style={{ color: "var(--color-success)" }}>
                  Draft complete. Live polling is paused.
                </p>
              ) : null}

              <section
                className="flex flex-col gap-2 p-4"
                style={{
                  background: state.is_my_pick ? "var(--color-accent-soft)" : "var(--color-surface-secondary)",
                  border: `var(--border-width-default) solid ${state.is_my_pick ? "var(--color-accent)" : "var(--color-border)"}`,
                }}
              >
                <span className="text-xs font-bold uppercase" style={{ color: "var(--color-text-muted)" }}>
                  On The Clock
                </span>
                <span style={{ font: "var(--type-section-title)" }}>
                  Pick {state.current_pick} · Round {state.current_round}
                </span>
                <span className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
                  {state.current_manager_name} · {state.current_team_name}
                </span>
                <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs" style={{ color: "var(--color-text-muted)" }}>
                  <span>{state.is_my_pick ? "On the clock" : state.picks_until_mine !== null ? `${state.picks_until_mine} picks away` : "Slot unavailable"}</span>
                  <span>
                    Your next picks: {state.my_upcoming_picks.length > 0 ? state.my_upcoming_picks.map((p) => `#${p}`).join(", ") : "Unavailable"}
                  </span>
                  <span>Recent run: {state.positional_run}</span>
                </div>
              </section>

              <section className="flex flex-col gap-3" aria-labelledby="live-draft-recs-heading">
                <SectionHeading id="live-draft-recs-heading">
                  Who should I draft next?
                </SectionHeading>
                {state.recommendations.length === 0 ? (
                  <EmptyState title="No recommendations are available yet." />
                ) : (
                  <div className="flex flex-col gap-3">
                    <RecommendationCard rec={state.recommendations[0]} primary />
                    {state.recommendations.length > 1 ? (
                      <div className="flex flex-col gap-2">
                        <span className="text-xs font-bold uppercase" style={{ color: "var(--color-text-muted)" }}>
                          Also consider
                        </span>
                        <div className="grid sm:grid-cols-2 gap-2">
                          {state.recommendations.slice(1).map((rec) => (
                            <RecommendationCard key={rec.player_id} rec={rec} primary={false} />
                          ))}
                        </div>
                      </div>
                    ) : null}
                  </div>
                )}
              </section>

              <RankingsBoard rows={state.rankings} leagueId={leagueId} leagueName={leagueName} />

              <section className="flex flex-col gap-3" aria-labelledby="live-draft-teams-heading">
                <SectionHeading id="live-draft-teams-heading">
                  Live Team Rankings
                </SectionHeading>
                <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                  Every fantasy roster reranked as Sleeper reports each pick: 60% starter strength, 30% total roster
                  value, 7% usable depth, 3% lineup coverage.
                </p>
                {state.team_rankings.length === 0 ? (
                  <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
                    Team rankings will appear when draft rosters are available.
                  </p>
                ) : (
                  <div className="flex flex-col">
                    {state.team_rankings.map((row) => (
                      <TeamRankingRowView key={row.roster_id} row={row} />
                    ))}
                  </div>
                )}
              </section>

              <section className="flex flex-col gap-3" aria-labelledby="live-draft-board-heading">
                <SectionHeading id="live-draft-board-heading">
                  Draft Board
                </SectionHeading>
                <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                  Latest pick and your picks are highlighted.
                </p>
                {state.pick_rows.length === 0 ? (
                  <EmptyState title="No picks have been logged yet." subtitle="This board will fill as Sleeper reports selections." />
                ) : (
                  <div className="flex flex-col">
                    {[...state.pick_rows].reverse().map((row) => (
                      <PickRowView key={row.pick_no} row={row} />
                    ))}
                  </div>
                )}
              </section>

              {state.status === "drafting" || state.status === "paused" ? (
                <LiveDraftTradeEvaluator
                  leagueId={leagueId}
                  draftId={selectedDraftId}
                  draftedRows={state.pick_rows}
                  lens={lens}
                />
              ) : null}

              <div className="flex items-center justify-between gap-3">
                <button
                  type="button"
                  onClick={onRefresh}
                  className="px-3 py-2 text-sm font-bold"
                  style={{ color: "var(--color-text-secondary)", border: "var(--border-width-default) solid var(--color-border)" }}
                >
                  Refresh Draft
                </button>
                <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                  Last updated: {state.last_updated} · Polls every 12s
                </span>
              </div>
            </>
          )}
        </>
      )}
      <ValuesCredit />
    </main>
  );
}
