"use client";

import { useEffect, useRef, useState } from "react";

import { api, type PlayerAward, type QuickViewResponse, type WeeklyStatPoint } from "@/lib/api";
import type { PlayerQuickViewIdentity } from "@/context/PlayerQuickViewContext";
import { ModelRadarChart } from "@/components/ModelRadarChart";
import { OvrGauge } from "@/components/OvrGauge";
import { PlayerAvatar } from "@/components/PlayerAvatar";
import { PositionBadge } from "@/components/PositionBadge";
import { WeeklyPointsPanel } from "@/components/WeeklyPointsChart";
import { formatRank, formatScore } from "@/lib/leagueRankingsPresentation";
import { waiverInjuryDisplay } from "@/lib/waiversPresentation";
import {
  SUB_RATING_DISPLAY,
  awardTierTone,
  overallRatingBand,
  ordinal,
  seasonStatGroups,
  statPercentileBand,
} from "@/lib/playerQuickViewPresentation";

/**
 * Player Quick View (Revision 22) — the web port of app.py's Player Quick
 * View pop-up (modules/player_quick_view.py), opened by
 * usePlayerQuickView().openPlayer(identity) from any player identity row.
 *
 * Deliberately a condensed MODAL, not mobile's full-screen PlayerDetail
 * push: coridian_ asked for "the popups like pqv", and app.py's own PQV is
 * itself a dialog (DECISION_SURFACE_DIALOG_CSS) with a separate, bigger
 * "Open Profile" destination for the full dossier — web-next has no such
 * full-profile route yet, so this modal is deliberately scoped to what a
 * *quick* look needs: identity, value/rank, health/usage signals, season
 * stats with position percentiles, the Model sub-rating chips + Decision
 * Fit sentence, verified awards, and bio — not career season-by-season
 * history or the news/schedule tabs mobile's deeper screen also carries.
 *
 * Identity (name/team/position/photo) is NOT part of GET .../quick-view's
 * response (that endpoint is league-independent and assumes the caller
 * already has it — see lib/api.ts's QuickViewResponse docstring), so it
 * comes from the `identity` prop a caller's existing row data already
 * carries. The portrait is a real PlayerAvatar (Sleeper's headshot CDN,
 * tier-colored ring) — coridian_, 2026-10-16: "still need player pfp in
 * pqv" — falling back to a blank ringed circle for a player with no photo
 * on file, same as every other avatar in the app.
 */
export function PlayerQuickView({
  identity,
  onClose,
}: {
  identity: PlayerQuickViewIdentity;
  onClose: () => void;
}) {
  const dialogRef = useRef<HTMLDivElement | null>(null);
  const closeButtonRef = useRef<HTMLButtonElement | null>(null);
  const [detail, setDetail] = useState<QuickViewResponse | null>(null);
  const [awards, setAwards] = useState<PlayerAward[]>([]);
  const [weeklyStats, setWeeklyStats] = useState<{ season: number; weeks: WeeklyStatPoint[] } | null>(null);
  const [loading, setLoading] = useState(true);

  // Swipe-down-to-dismiss, via the drag handle only (not the whole modal —
  // the body itself needs to stay normally scrollable). Pointer events
  // cover touch and mouse in one handler; dragStartY stays a ref since it's
  // write-only bookkeeping between pointerdown/pointermove, not something a
  // render needs to react to.
  const dragStartY = useRef<number | null>(null);
  const [dragY, setDragY] = useState(0);
  const [isDragging, setIsDragging] = useState(false);
  const DISMISS_THRESHOLD_PX = 110;

  function handleDragStart(event: React.PointerEvent<HTMLDivElement>) {
    dragStartY.current = event.clientY;
    setIsDragging(true);
    event.currentTarget.setPointerCapture(event.pointerId);
  }
  function handleDragMove(event: React.PointerEvent<HTMLDivElement>) {
    if (dragStartY.current === null) return;
    setDragY(Math.max(0, event.clientY - dragStartY.current));
  }
  function handleDragEnd() {
    if (dragY > DISMISS_THRESHOLD_PX) {
      onClose();
      return;
    }
    dragStartY.current = null;
    setIsDragging(false);
    setDragY(0);
  }
  const [loadError, setLoadError] = useState(false);

  // Fetch detail/awards for this player. The provider mounts one
  // PlayerQuickView per player_id (key={identity.player_id} — see
  // PlayerQuickViewContext.tsx), so a new player is always a fresh mount
  // with fresh initial state rather than a reset done imperatively here.
  // Both calls are independent (one 404-shaped reason never blocks the
  // other). Weekly stats (coridian_, 2026-10-17: "the PQV is missing info
  // like the week by week points") is fetched separately via .catch
  // rather than inside the same Promise.all — a missing/failed weekly-stats
  // fetch must never block the identity/value/model data the rest of this
  // modal actually needs, same reasoning as awards. Reuses the exact same
  // GET .../weekly-stats endpoint + WeeklyPointsPanel component Player
  // Compare's dual chart already does, not a new fetch/chart.
  useEffect(() => {
    let cancelled = false;

    Promise.all([api.getPlayerQuickView(identity.player_id), api.getPlayerAwards(identity.player_id)])
      .then(([quickView, awardsResponse]) => {
        if (cancelled) return;
        setDetail(quickView);
        setAwards(awardsResponse.ok ? awardsResponse.awards : []);
      })
      .catch(() => {
        if (cancelled) return;
        setLoadError(true);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    api
      .getPlayerWeeklyStats(identity.player_id)
      .then((response) => {
        if (cancelled) return;
        setWeeklyStats({ season: response.season, weeks: response.weeks });
      })
      .catch(() => {
        // Soft-fail: the rest of the modal is still useful without this.
      });

    return () => {
      cancelled = true;
    };
  }, [identity.player_id]);

  // Focus the close button on open, restore body scroll on close — the
  // minimal accessible-modal contract (focus moves into the dialog, page
  // behind it stops scrolling) without pulling in a dialog library.
  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    closeButtonRef.current?.focus();
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, []);

  function handleKeyDown(event: React.KeyboardEvent<HTMLDivElement>) {
    if (event.key === "Escape") {
      event.stopPropagation();
      onClose();
      return;
    }
    if (event.key !== "Tab") return;
    const container = dialogRef.current;
    if (!container) return;
    const focusable = container.querySelectorAll<HTMLElement>(
      'button, a[href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
    );
    if (focusable.length === 0) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  const stats = detail?.stats ?? null;
  const bio = detail?.bio ?? null;
  const model = detail?.model ?? null;
  const injury = waiverInjuryDisplay(identity.injury_status);
  const overallRating = identity.overall_rating ?? stats?.overall_rating ?? null;
  const name = identity.name || `Player ${identity.player_id}`;

  return (
    <div
      className="pqv-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div
        ref={dialogRef}
        className="pqv-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="pqv-name"
        onKeyDown={handleKeyDown}
        style={{
          transform: dragY ? `translateY(${dragY}px)` : undefined,
          transition: isDragging ? "none" : "transform 180ms ease",
        }}
      >
        {/* coridian_, 2026-10-18: "Also need that moving background behind
            the pqv" — same field/sweep texture as the GM orb sheet,
            contained to this modal rather than the viewport-fixed global
            layer (which sits behind this modal's own opaque background). */}
        <div className="pqv-field" aria-hidden="true" />
        <div className="pqv-sweep" aria-hidden="true" />
        <div
          className="pqv-drag-handle"
          onPointerDown={handleDragStart}
          onPointerMove={handleDragMove}
          onPointerUp={handleDragEnd}
          onPointerCancel={handleDragEnd}
          aria-hidden="true"
        >
          <span className="pqv-drag-handle-bar" />
        </div>
        <button
          ref={closeButtonRef}
          type="button"
          className="pqv-close"
          aria-label="Close player details"
          onClick={onClose}
        >
          ×
        </button>

        <div className="pqv-scroll">

        {/* coridian_, 2026-10-18: "rework the top of the pqv with a bigger
            pfp and reorganized top" — the 88px avatar sat beside a narrow
            column squeezing name, meta, the OVR gauge + rank cells, AND the
            chip row all into the same cramped width. Bigger avatar (112px)
            now anchors just identity (name/meta) beside it; the rank strip
            and signal chips drop below as their own full-width rows
            instead of fighting the avatar for horizontal space. */}
        <header className="pqv-hero">
          <PlayerAvatar playerId={identity.player_id} tier={identity.tier} size={112} />
          <div className="pqv-hero-copy">
            {identity.sourceLabel ? <div className="pqv-source-label">{identity.sourceLabel}</div> : null}
            <h2 id="pqv-name" className="pqv-name">
              {name}
            </h2>
            <div className="pqv-meta">
              <PositionBadge position={identity.position} />
              <span>{identity.team || "FA"}</span>
              <span>·</span>
              <span>Age {identity.age ?? "N/A"}</span>
            </div>
          </div>
        </header>

        <div className="pqv-rank-strip">
          <OvrGauge rating={overallRating} size="lg" />
          <div className="pqv-rank-cells">
            {identity.score != null ? (
              <div className="pqv-rank-cell">
                <span>Value</span>
                <strong>{formatScore(identity.score)}</strong>
              </div>
            ) : null}
            {identity.overall_rank ? (
              <div className="pqv-rank-cell">
                <span>Overall rank</span>
                <strong>{formatRank(identity.overall_rank)}</strong>
              </div>
            ) : null}
            {identity.position_rank ? (
              <div className="pqv-rank-cell">
                <span>Position rank</span>
                <strong>
                  {identity.position || ""}
                  {identity.position_rank}
                </strong>
              </div>
            ) : null}
          </div>
        </div>
        <div className="pqv-signal-row">
          {identity.tier ? <span className="pqv-chip">{identity.tier}</span> : null}
          {identity.opportunity_label ? <span className="pqv-chip">{identity.opportunity_label}</span> : null}
          {injury.label ? (
            <span className={`pqv-chip pqv-chip--${injury.tone}`}>Health: {injury.label}</span>
          ) : null}
          {model?.usage_trend ? (
            <span className="pqv-chip">
              {model.usage_trend.arrow} {model.usage_trend.trend_pct}% usage · {model.usage_trend.confidence_label}
            </span>
          ) : null}
        </div>

        <div className="pqv-body">
          {loading ? (
            <p className="pqv-status-text">Loading player detail…</p>
          ) : loadError ? (
            <p className="pqv-status-text">Couldn&apos;t load this player&apos;s detail right now.</p>
          ) : (
            <>
              {model?.decision_fit_narrative ? (
                <section className="pqv-decision-fit">
                  <h3>Decision Fit</h3>
                  <p>{model.decision_fit_narrative}</p>
                </section>
              ) : null}

              {weeklyStats && weeklyStats.weeks.some((week) => week.fantasy_points_ppr != null) ? (
                <section className="pqv-stat-season">
                  <h3>Week by Week</h3>
                  <WeeklyPointsPanel
                    name={identity.name || "This player"}
                    weeks={weeklyStats.weeks}
                    season={weeklyStats.season}
                    gradientId="pqv-weekly-fill"
                  />
                </section>
              ) : null}

              {stats?.seasons.map((season) => (
                <section key={season.label} className="pqv-stat-season">
                  <h3>
                    {season.label}
                    {season.games != null ? ` · ${season.games} games` : ""}
                  </h3>
                  {seasonStatGroups(season).map((group) => (
                    <StatGroup key={group.title} title={group.title} items={group.items} />
                  ))}
                </section>
              ))}

              {stats && stats.college.length > 0 ? (
                <section className="pqv-stat-season">
                  <h3>College</h3>
                  <StatGroup title="College Stats" items={stats.college} hideTitle />
                </section>
              ) : null}

              {awards.length > 0 ? <AwardsStrip awards={awards} /> : null}

              {bio ? <BioGrid bio={bio} /> : null}

              {/* coridian_, 2026-10-18: "the model section needs to be
                  moved all the way to the bottom and have that multi-axis
                  thing still" — Model used to sit right after Decision
                  Fit; now the last section, after stats/college/awards/
                  bio. SubRatingRow (model) renders a real 5-axis radar
                  chart (ModelRadarChart) when every factor is present,
                  same as modules/player_quick_view.py's own
                  model_radar_chart_html — the flat chip row stays the
                  fallback for a player without a full read on every
                  factor, same split the Python source makes. */}
              {model ? <SubRatingRow model={model} /> : null}
            </>
          )}
        </div>

        {identity.leagueId ? (
          <div className="pqv-actions">
            <a
              className="pqv-action-link"
              href={`/player-compare/${encodeURIComponent(identity.leagueId)}?a=${encodeURIComponent(
                identity.player_id,
              )}&name=${encodeURIComponent(identity.leagueName || "")}`}
            >
              Compare this player
            </a>
          </div>
        ) : null}
        </div>
      </div>
    </div>
  );
}

function StatGroup({
  title,
  items,
  hideTitle = false,
}: {
  title: string;
  items: { label: string; value: string; note: string; percentile: number | null }[];
  hideTitle?: boolean;
}) {
  if (items.length === 0) return null;
  return (
    <div className="pqv-stat-group">
      {hideTitle ? null : <h4>{title}</h4>}
      <div className="pqv-stat-grid">
        {items.map((item) => (
          <div key={item.label} className="pqv-stat-row">
            <div className="pqv-stat-label">{item.label}</div>
            <div className="pqv-stat-value">{item.value}</div>
            {item.percentile != null ? (
              <div className={`pqv-percentile pqv-percentile--${statPercentileBand(item.percentile)}`}>
                <span className="pqv-percentile-bar">
                  <span style={{ width: `${Math.max(1, Math.min(100, Math.round(item.percentile)))}%` }} />
                </span>
                <span className="pqv-percentile-label">{ordinal(Math.round(item.percentile))} pct</span>
              </div>
            ) : null}
          </div>
        ))}
      </div>
    </div>
  );
}

function SubRatingRow({
  model,
}: {
  model: {
    market_rating?: number | null;
    opportunity_rating?: number | null;
    scarcity_rating?: number | null;
    role_rating?: number | null;
    durability_rating?: number | null;
  };
}) {
  const chips = SUB_RATING_DISPLAY.map(({ key, abbr, label }) => ({
    abbr,
    label,
    rating: model[key],
  })).filter((chip) => chip.rating != null);
  if (chips.length === 0) return null;
  const hasFullRead = SUB_RATING_DISPLAY.every(({ key }) => model[key] != null);
  return (
    <section className="pqv-model-row" aria-label="Model sub-ratings">
      <h3>Model</h3>
      {hasFullRead ? (
        <ModelRadarChart model={model} />
      ) : (
        <div className="pqv-sub-rating-row">
          {chips.map((chip) => (
            <span
              key={chip.abbr}
              className={`pqv-sub-rating-chip pqv-sub-rating-chip--${overallRatingBand(chip.rating as number)}`}
              aria-label={`${chip.label} rating ${chip.rating} of 99`}
            >
              <span className="pqv-sub-rating-chip-label">{chip.abbr}</span>
              <strong>{chip.rating}</strong>
            </span>
          ))}
        </div>
      )}
    </section>
  );
}

function AwardsStrip({ awards }: { awards: PlayerAward[] }) {
  return (
    <section className="pqv-awards" aria-label="Player awards">
      <h3>Awards</h3>
      <div className="pqv-awards-row">
        {awards.map((award) => (
          <span key={award.badge_id} className={`pqv-award pqv-award--${awardTierTone(award.tier)}`} title={award.description}>
            {award.short_label}
            {award.season ? ` · ${award.season}` : ""}
          </span>
        ))}
      </div>
    </section>
  );
}

function BioGrid({
  bio,
}: {
  bio: {
    years_in_league: string;
    draft_capital: string;
    college: string;
    height: string;
    weight: string;
    bye_week: string;
    contract_status: string;
  };
}) {
  const rows: Array<[string, string]> = [
    ["Experience", bio.years_in_league],
    ["Draft capital", bio.draft_capital],
    ["College", bio.college],
    ["Height", bio.height],
    ["Weight", bio.weight],
    ["Bye week", bio.bye_week],
    ["Contract", bio.contract_status],
  ].filter(([, value]) => Boolean(value)) as Array<[string, string]>;
  if (rows.length === 0) return null;
  return (
    <section className="pqv-bio" aria-label="Player bio">
      <h3>Bio</h3>
      <div className="pqv-bio-grid">
        {rows.map(([label, value]) => (
          <div key={label} className="pqv-bio-cell">
            <span>{label}</span>
            <strong>{value}</strong>
          </div>
        ))}
      </div>
    </section>
  );
}
