"use client";

import { useEffect, useRef, useState } from "react";

import { api, type PlayerAward, type QuickViewResponse } from "@/lib/api";
import type { PlayerQuickViewIdentity } from "@/context/PlayerQuickViewContext";
import { BeginnerHelp } from "@/components/BeginnerHelp";
import { ModelRadarChart } from "@/components/ModelRadarChart";
import { OvrGauge } from "@/components/OvrGauge";
import { PlayerAvatar } from "@/components/PlayerAvatar";
import { PlayerTrendsPanel } from "@/components/PlayerTrendsPanel";
import { PositionBadge } from "@/components/PositionBadge";
import { SheetHandle } from "@/components/SheetHandle";
import { CHART_HEIGHT } from "@/components/WeeklyPointsChart";
import { formatRank, formatScore } from "@/lib/leagueRankingsPresentation";
import { resolvePlayerTier } from "@/lib/playerTier";
import { useSheetDragDismiss } from "@/lib/useSheetDragDismiss";
import { waiverInjuryDisplay } from "@/lib/waiversPresentation";
import {
  SUB_RATING_DISPLAY,
  awardTierTone,
  overallRatingBand,
  ordinal,
  seasonStatGroups,
  statPercentileBand,
  tierOpportunityMismatchCaption,
} from "@/lib/playerQuickViewPresentation";
import { ValuesCredit } from "@/components/ValuesCredit";

/**
 * Player Quick View (Revision 22) — the web port of app.py's Player Quick
 * View pop-up (modules/player_quick_view.py), opened by
 * usePlayerQuickView().openPlayer(identity) from any player identity row.
 *
 * Deliberately a condensed MODAL, not mobile's full-screen PlayerDetail
 * push: coridian_ asked for "the popups like pqv", and app.py's own PQV is
 * itself a dialog (DECISION_SURFACE_DIALOG_CSS) with a separate, bigger
 * "Open Profile" destination for the full dossier. This modal stays scoped
 * to what a *quick* look needs: identity, value/rank, health/usage signals,
 * season stats with position percentiles, the Model sub-rating chips +
 * Decision Fit sentence, verified awards, and bio — not career
 * season-by-season history or the schedule tab mobile's deeper screen also
 * carries. The "Open Full Profile" link in this modal's actions row (below)
 * is the real full-profile destination (players/[leagueId]/[playerId],
 * PlayerProfileContent.tsx) — mobile's PlayerDetailScreen.tsx's Stats/
 * Trends/Schedule/Career/Model tabs, ported (coridian_, 2026-10-19: "the
 * pqv on the app has tabs that the site doesnt. Thats a consistency
 * error" — see docs/roadmap.md's "PQV parity gap" entry).
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
  const [loading, setLoading] = useState(true);

  // Swipe-down-to-dismiss on touch devices: the shared sheet gesture (see
  // lib/useSheetDragDismiss.ts). Only closes when the body is scrolled to
  // its top, so scrolling back up inside a long PQV never closes it.
  const { sheetRef, sheetStyle } = useSheetDragDismiss({ onDismiss: onClose });
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
        ref={(node) => {
          dialogRef.current = node;
          sheetRef.current = node;
        }}
        className="pqv-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="pqv-name"
        onKeyDown={handleKeyDown}
        style={sheetStyle}
      >
        {/* coridian_, 2026-10-18: "Also need that moving background behind
            the pqv" — same field/sweep texture as the GM orb sheet,
            contained to this modal rather than the viewport-fixed global
            layer (which sits behind this modal's own opaque background). */}
        <div className="pqv-field" aria-hidden="true" />
        <div className="pqv-sweep" aria-hidden="true" />
        <SheetHandle />
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

        {/* coridian_, 2026-10-19: "theres nothing to the right of pfp and
            name and thats just wasted space. also the elite tag should be
            right under pfp" / "Overall and usage and anything else thats
            up there and not positioned properly" — the prior layout (PR
            from 2026-10-18) fixed the avatar/copy from fighting the rank
            strip and chips for width, but then left that same width empty
            below the name on anything wider than the ~480px bottom-sheet
            breakpoint. Tier now sits under the avatar (matching its own
            prestige-ring color, same as before); OVR gauge, rank cells,
            and the usage-trend chip move up beside the name/meta instead
            of dropping to their own full-width rows underneath. */}
        <header className="pqv-hero">
          <div className="pqv-hero-avatar-col">
            <PlayerAvatar playerId={identity.player_id} tier={identity.tier} size={112} />
            {identity.tier ? (
              <span
                className="pqv-chip pqv-tier-chip"
                style={{ borderColor: `var(${resolvePlayerTier(identity.tier).colorVar})`, color: `var(${resolvePlayerTier(identity.tier).colorVar})` }}
              >
                {identity.tier}
              </span>
            ) : null}
          </div>
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
            {/* coridian_, 2026-10-18: "Starter and usage still need to be
                color coordinated" — usage uses its own real tone
                (positive/negative) the API already computes
                (modules.rankings.recency_trend_display), not a new rule. */}
            {model?.usage_trend ? (
              <span
                className={`pqv-chip pqv-chip--${model.usage_trend.tone === "positive" ? "positive" : "danger"}`}
                title={model.usage_trend.detail}
              >
                {model.usage_trend.arrow} {model.usage_trend.trend_pct}% usage · {model.usage_trend.confidence_label}
              </span>
            ) : null}
            {/* coridian_, 2026-10-19: "was there any way for us to predict
                (scenario) something like cam skattebo having 0 snaps and
                relaying that to USERS?" — a depth-chart-order move is a
                leading indicator games-played/injury-status signals can't
                catch (a coaching-decision role change has no injury
                signal at all). */}
            {model?.depth_chart_note ? <p className="pqv-tier-mismatch-note">{model.depth_chart_note}</p> : null}
          </div>
        </header>

        <div className="pqv-signal-row">
          {identity.opportunity_label ? <span className="pqv-chip">{identity.opportunity_label}</span> : null}
          {injury.label ? (
            <span className={`pqv-chip pqv-chip--${injury.tone}`}>Health: {injury.label}</span>
          ) : null}
        </div>
        {/* coridian_, 2026-10-19 (screenshot): "the contributor tag doesnt
            make sense if he hasnt been playing much" — tier (season-long
            value) and opportunity_label (right-now depth-chart read) can
            legitimately disagree; this names the specific combination that
            caused the confusion instead of leaving two silently
            contradicting chips. */}
        {tierOpportunityMismatchCaption(identity.tier, identity.opportunity_label) ? (
          <p className="pqv-tier-mismatch-note">{tierOpportunityMismatchCaption(identity.tier, identity.opportunity_label)}</p>
        ) : null}
        {/* Beginner-only explanations of the hero's value/OVR/tier labels
            (lib/experienceCopy.ts) — renders nothing for advanced/unset. */}
        {identity.score != null ? <BeginnerHelp term="playerValue" className="mt-1" /> : null}
        {overallRating != null ? <BeginnerHelp term="overallRating" className="mt-1" /> : null}
        {identity.tier ? <BeginnerHelp term="playerTier" className="mt-1" /> : null}

        <div className="pqv-body">
          {loading ? (
            <PqvBodySkeleton />
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

              <PlayerTrendsPanel
                playerId={identity.player_id}
                name={identity.name || "This player"}
                gradientId="pqv-weekly-fill"
              />

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
            {/* coridian_, 2026-10-19: "the pqv on the app has tabs that the
                site doesnt. Thats a consistency error" — this is the real
                product fix: a destination for mobile's Stats/Trends/
                Schedule/Career/Model tabs, which this condensed modal
                deliberately never carries (see this file's own header doc
                comment). */}
            <a
              className="pqv-action-link"
              href={`/players/${encodeURIComponent(identity.leagueId)}/${encodeURIComponent(
                identity.player_id,
              )}?name=${encodeURIComponent(identity.leagueName || "")}`}
            >
              Open Full Profile
            </a>
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
        <ValuesCredit className="text-center" />
        </div>
      </div>
    </div>
  );
}

/** coridian_, 2026-10-20: "it expands the background of the PQV as those
 * modules load in and looks very clunky" — rendered in place of the old
 * single "Loading player detail…" line while `detail`/`awards` are in
 * flight. Shaped/sized like the content that replaces it (a decision-fit
 * line, the trends chart's own CHART_HEIGHT footprint, a few stat-tile
 * grids using the exact same .pqv-stat-row/.pqv-stat-grid classes as the
 * real stats, a model chip row, an awards chip row) so the modal's height
 * is already roughly reserved before the fetch resolves — no visible
 * "grow" when the real content swaps in. Decorative only (aria-hidden);
 * the real status text stays as an sr-only live region right below it so
 * assistive tech and existing "Loading player detail" assertions both
 * still see it. */
function PqvBodySkeleton() {
  return (
    <>
      <div aria-hidden="true">
        <div className="pqv-skeleton-section">
          <div className="pqv-skeleton-line pqv-skeleton-line--wide" />
          <div className="pqv-skeleton-line pqv-skeleton-line--mid" />
        </div>
        <div className="pqv-skeleton-section">
          <div className="pqv-skeleton-line pqv-skeleton-line--label" />
          <div className="pqv-skeleton-chart" style={{ height: CHART_HEIGHT }} />
        </div>
        {["Production", "Fantasy", "Usage"].map((group) => (
          <div className="pqv-skeleton-section" key={group}>
            <div className="pqv-skeleton-line pqv-skeleton-line--label" />
            <div className="pqv-stat-grid">
              {Array.from({ length: 6 }, (_, index) => (
                <div key={index} className="pqv-stat-row pqv-skeleton-tile">
                  <div className="pqv-skeleton-line pqv-skeleton-line--short" />
                  <div className="pqv-skeleton-line pqv-skeleton-line--mid" />
                </div>
              ))}
            </div>
          </div>
        ))}
        <div className="pqv-skeleton-section">
          <div className="pqv-skeleton-line pqv-skeleton-line--label" />
          <div className="pqv-skeleton-chip-row">
            {Array.from({ length: 5 }, (_, index) => (
              <div key={index} className="pqv-skeleton-chip" />
            ))}
          </div>
        </div>
      </div>
      <p className="sr-only" role="status">
        Loading player detail…
      </p>
    </>
  );
}

/** Exported (not just this modal's private renderer) so the full Player
 * Profile page (players/[leagueId]/[playerId]) can reuse the identical
 * stat-row + percentile markup for its Stats tab instead of a second
 * copy — see that page's own module doc comment. */
export function StatGroup({
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
              <div
                className={`pqv-percentile pqv-percentile--${statPercentileBand(item.percentile)}`}
                title={`${ordinal(Math.round(item.percentile))} percentile at ${item.label}`}
              >
                <span className="pqv-percentile-dot" aria-hidden="true" />
                <span className="pqv-percentile-label">{ordinal(Math.round(item.percentile))} pct</span>
              </div>
            ) : null}
          </div>
        ))}
      </div>
    </div>
  );
}

/** Exported for the full Player Profile page's Model tab — same
 * chip-row/radar-chart renderer, not a second copy. */
export function SubRatingRow({
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

/** Exported for the full Player Profile page, which (like mobile's own
 * PlayerDetailScreen) shows Awards tab-agnostically rather than inventing a
 * sixth tab for it. */
export function AwardsStrip({ awards }: { awards: PlayerAward[] }) {
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

/** Exported for the full Player Profile page, same tab-agnostic treatment
 * as AwardsStrip above. */
export function BioGrid({
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
