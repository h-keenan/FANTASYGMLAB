"use client";

import { ToneBadge } from "@/components/ToneBadge";
import { ExplorerLeagueProvider } from "@/context/ExplorerLeagueContext";
import dynamic from "next/dynamic";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState, type ReactNode } from "react";

import { api, type PlayerAward, type PlayerNewsResponse, type QuickViewResponse } from "@/lib/api";
import type { PlayerQuickViewIdentity } from "@/context/PlayerQuickViewContext";
import { BeginnerHelp } from "@/components/BeginnerHelp";
import { BEGINNER_HELP } from "@/lib/experienceCopy";
import { DecisionFitCard, PlayerHeroHeader } from "@/components/PlayerHeroHeader";
import { PlayerUsageBlock } from "@/components/PlayerUsageBlock";
import { SeasonStatsRows } from "@/components/SeasonStatsRows";
import { HeadlineTiles } from "@/components/StatRows";
import { headlineRows } from "@/lib/statRowsPresentation";
import { PlayerLeagueActions } from "@/components/PlayerLeagueActions";
import { PlayerValueHistory } from "@/components/PlayerValueHistory";
import { PlayerTrendsPanel } from "@/components/PlayerTrendsPanel";
import { PercentileExplorerSheet } from "@/components/PercentileExplorerSheet";
import { SheetHandle } from "@/components/SheetHandle";
import { orderPlayerSheetTabs, type SheetSnap } from "@/lib/playerAnatomy";
import { usePlayerQuickView } from "@/context/PlayerQuickViewContext";
import { explorerStatKey } from "@/lib/percentileExplorer";
import { CHART_HEIGHT } from "@/components/weeklyPointsChartHeight";
import { OverlayBack } from "@/components/OverlayBack";
import { useOverlay } from "@/lib/useOverlay";
import { useSheetDragDismiss } from "@/lib/useSheetDragDismiss";
import { AvailabilityBlock, LatestNewsSection } from "@/components/PlayerQuickViewNews";
import { Tabs } from "@/components/Tabs";
import { pqvBioForContext, pqvRealWorld } from "@/lib/pqvContext";
import { rowsAsOf, simAsOfSeason } from "@/lib/simAsOf";
import { cleanInjuryLabel, playerProfileNewsHref } from "@/lib/playerAvailabilityPresentation";
import { waiverInjuryDisplay } from "@/lib/waiversPresentation";
import {
  SUB_RATING_DISPLAY,
  awardTierTone,
  overallRatingBand,
  ordinal,
  rookieBadge,
  seasonStatGroups,
  statPercentileBand,
  tierOpportunityMismatchCaption,
  opportunityUsageCaption,
} from "@/lib/playerQuickViewPresentation";
import { ValuesCredit } from "@/components/ValuesCredit";
import { BadgeLegendSheet, PlayerBadges } from "@/components/ui/PlayerBadge";
import { badgeFromInjury, badgeFromTag } from "@/lib/playerBadges";
import { SkeletonBlock } from "@/components/Skeleton";

// The radar is the only thing here that needs recharts (~110 KB gzip); this file
// is also imported statically by the full Player Profile page. The placeholder
// is the chart's exact footprint, so the swap does not move anything.
const ModelRadarChart = dynamic(() => import("@/components/ModelRadarChart").then((m) => m.ModelRadarChart), {
  ssr: false,
  loading: () => <div style={{ width: "100%", maxWidth: "16rem", height: 220, margin: "0 auto" }} aria-hidden="true" />,
});

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
/** The Fantasy Sim's own tab contents inside the Player Quick View (see `simSections`). */
export interface SimPqvSections {
  overview: ReactNode;
  /** The hero's letter-grade tile. Present in the sim: the numeric Player score ring, Value tile and overall / position ranks never show there. */
  heroGrade?: ReactNode;
  outlook?: ReactNode;
  scouting?: ReactNode;
  history?: ReactNode;
  /** The two hero tiles shown in place of Value and Usage (the sim never shows the model's value). */
  heroTiles?: { label: string; value: string; note: string }[];
  /** Real-NFL record cut to the as-of season (career + game log), shown first in the Stats tab. */
  stats?: ReactNode;
}

const TAG_TONE_COLOR = {
  success: "var(--color-success)",
  accent: "var(--color-accent)",
  warning: "var(--color-warning)",
  danger: "var(--color-danger)",
  muted: "var(--color-text-secondary)",
} as const;

export function PlayerQuickView({
  identity,
  onClose,
  simOverlay,
  asOfSeason,
  simSections,
  remote = true,
}: {
  identity: PlayerQuickViewIdentity;
  onClose: () => void;
  /**
   * Fantasy Sim: game-specific sections (this sim's projection band, status,
   * week-by-week outlook, results, owner, actions) rendered right under the
   * hero, so the game's player detail is this same Quick View. Omit everywhere else.
   */
  simOverlay?: ReactNode;
  /**
   * Fantasy Sim only: the last fully finished real season at the sim's start (see lib/simAsOf.ts). Real season stats and
   * awards are cut to it; the in-progress real season, current usage / trend charts and value history never show.
   */
  asOfSeason?: number;
  /**
   * Fantasy Sim, split by tab (preferred over `simOverlay`): the game's own Overview, Outlook (week-by-week), Scouting
   * (generated rookies) and History (draft slot, moves, seasons). Present = this is the sim's world, not the real one.
   */
  simSections?: SimPqvSections;
  /** false for a synthetic sim player with no real data behind the id: same layout, no remote fetches. */
  remote?: boolean;
}) {
  // Fantasy Sim (coridian_, 2026-11-13: "inside of Fantasy Sim there should not be real news in there whatsoever"): the sim
  // overlay marks this as the game's own world. Real news, real injury / availability notes, the real depth-chart note and
  // the real bye never show here; the sim's own status, news and outlook (simOverlay) are the only source.
  const sim: SimPqvSections | null = simSections ?? (simOverlay != null ? { overview: simOverlay } : null);
  const isSim = sim != null;
  const realWorld = pqvRealWorld(isSim);
  const pathname = usePathname();
  const dialogRef = useRef<HTMLDivElement | null>(null);
  const closeButtonRef = useRef<HTMLButtonElement | null>(null);
  const [legendOpen, setLegendOpen] = useState(false);
  // Peek sheet (coridian_ pick 1b): opens half height with the header and pills, drag the handle up for full.
  const [snap, setSnap] = useState<SheetSnap>("peek");
  const [detail, setDetail] = useState<QuickViewResponse | null>(null);
  const [awards, setAwards] = useState<PlayerAward[]>([]);
  const [loading, setLoading] = useState(remote);
  // News loads lazily and independently: it never gates the sheet. null =
  // not loaded (or failed -> section renders nothing).
  const [news, setNews] = useState<PlayerNewsResponse | null>(null);
  const [newsLoading, setNewsLoading] = useState(remote && realWorld.fetchNews);

  // Swipe-down-to-dismiss on touch devices: the shared sheet gesture (see
  // lib/useSheetDragDismiss.ts). Only closes when the body is scrolled to
  // its top, so scrolling back up inside a long PQV never closes it.
  const { sheetRef, sheetStyle, backdropStyle } = useSheetDragDismiss({ onDismiss: onClose });
  // One pop-up at a time (lib/overlayStack.ts): opened from another pop-up this replaces it on screen and gets "‹ Back".
  const overlay = useOverlay({ title: identity.name || "Player", onClose });
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
    if (!remote) return;
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
  }, [identity.player_id, remote]);

  useEffect(() => {
    if (!remote || !realWorld.fetchNews) return;
    let cancelled = false;
    api
      .getPlayerNews(identity.player_id, 3, { groupDuplicates: true })
      .then((result) => {
        if (!cancelled && result.ok) setNews(result);
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setNewsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [identity.player_id, remote, realWorld.fetchNews]);

  // Focus moves into the dialog whenever it becomes the visible pop-up (first open, or returning from one opened on top).
  // Page scroll lock, history and layering belong to the overlay runtime, not to this shell.
  const visible = !overlay.hidden;
  useEffect(() => {
    if (visible) closeButtonRef.current?.focus();
  }, [visible]);

  function handleKeyDown(event: React.KeyboardEvent<HTMLDivElement>) {
    if (event.key === "Escape") {
      event.stopPropagation();
      overlay.back();
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

  // Fantasy Sim "as-of" cut: only seasons up to the sim's start; nothing current (usage trend / profile, value history).
  const asOf = isSim ? (asOfSeason ?? simAsOfSeason(null)) : null;
  const stats = detail?.stats ? (asOf != null ? { ...detail.stats, seasons: rowsAsOf(detail.stats.seasons, asOf) } : detail.stats) : null;
  const bio = detail?.bio ?? null;
  const model = detail?.model ? (asOf != null ? { ...detail.model, usage_trend: null, usage_profile: null } : detail.model) : null;
  const shownAwards = asOf != null ? rowsAsOf(awards, asOf) : awards;
  const resolved = detail?.identity ?? null;
  // The server's availability block (directory status) wins; the row's raw
  // status only drives the chip until it arrives, with a clean label.
  const availability = realWorld.showAvailability ? (resolved?.availability ?? null) : null;
  const injuryLabel = cleanInjuryLabel(identity.injury_status);
  const injury = {
    label: availability ? null : injuryLabel,
    tone: waiverInjuryDisplay(identity.injury_status).tone,
  };
  // Fantasy Sim: no numeric rating of any kind (the grade tile replaces the ring); the real world's score, value and ranks never show.
  const overallRating = isSim ? null : (identity.overall_rating ?? stats?.overall_rating ?? resolved?.overall_rating ?? null);
  const name = identity.name || resolved?.name || `Player ${identity.player_id}`;
  // What a remote tab shows instead of its content while the detail loads or when it failed (null = show the content).
  const bodyGate: ReactNode | null = loading ? (
    <PqvBodySkeleton />
  ) : !remote ? null : loadError ? (
    <p className="pqv-status-text">Couldn&apos;t load this player&apos;s detail right now.</p>
  ) : null;

  return (
    <div
      className="pqv-backdrop"
      style={backdropStyle}
      hidden={overlay.hidden}
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) overlay.closeAll();
      }}
    >
      <div
        ref={(node) => {
          dialogRef.current = node;
          sheetRef.current = node;
        }}
        className="pqv-modal"
        data-snap={snap}
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
        <SheetHandle snap={snap} onSnap={setSnap} />
        <OverlayBack overlay={overlay} />
        <button
          ref={closeButtonRef}
          type="button"
          className="pqv-close"
          aria-label="Close player details"
          onClick={overlay.closeAll}
        >
          ×
        </button>

        <div className="pqv-scroll">

        <PlayerHeroHeader
          playerId={identity.player_id}
          name={name}
          nameId="pqv-name"
          contextLabel={identity.sourceLabel}
          position={identity.position || resolved?.position}
          team={identity.team || resolved?.team}
          age={identity.age ?? resolved?.age ?? null}
          tier={identity.tier}
          score={isSim ? null : (identity.score ?? resolved?.value_score ?? null)}
          gradeTile={isSim ? (sim?.heroGrade ?? null) : null}
          valueNote={identity.value_note ?? resolved?.value_note}
          valueLabel={identity.value_label ?? null}
          avatarId={remote ? identity.player_id : null}
          loadingIdentity={loading}
          byeWeek={realWorld.showBye ? (resolved?.bye_week ?? null) : null}
          onByeThisWeek={realWorld.showBye ? (resolved?.on_bye_this_week ?? false) : false}
          unavailable={availability?.unavailable ?? false}
          overallRating={overallRating}
          overallRank={isSim ? null : identity.overall_rank}
          positionRank={isSim ? null : identity.position_rank}
          usageTrend={model?.usage_trend ?? null}
          simTiles={sim?.heroTiles ?? null}
          usageLoading={loading}
          valueChart={asOf != null ? null : <PlayerValueHistory playerId={identity.player_id} bare />}
          ovrChart={model && !isSim ? <SubRatingRow model={model} bare /> : null}
          depthChartNote={realWorld.showDepthChartNote ? model?.depth_chart_note : null}
          rookie={rookieBadge(bio)}
        />

        <div className="pqv-signal-row">
          {identity.opportunity_label ? <span className="pqv-chip">{identity.opportunity_label}</span> : null}
          {identity.tags?.length ? (
            <>
              <PlayerBadges badges={identity.tags.map((tag) => badgeFromTag(tag))} max={6} showDetail onLegend={() => setLegendOpen(true)} testId="pqv-badges" />
              {identity.tags.filter((tag) => !badgeFromTag(tag)).map((tag) => (
                <ToneBadge key={tag.key} label={tag.label} color={TAG_TONE_COLOR[tag.tone]} size="xs" truncate testId="pqv-tag" />
              ))}
            </>
          ) : injury.label ? (
            badgeFromInjury(injury.label) ? (
              <PlayerBadges badges={[{ kind: badgeFromInjury(injury.label)!, detail: injury.label }]} showDetail onLegend={() => setLegendOpen(true)} testId="pqv-badges" />
            ) : (
              <span className={`pqv-chip pqv-chip--${injury.tone}`}>Health: {injury.label}</span>
            )
          ) : null}
          <BadgeLegendSheet open={legendOpen} onClose={() => setLegendOpen(false)} />
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
        {opportunityUsageCaption(identity.opportunity_label, model?.usage_trend ?? null) ? (
          <p className="pqv-tier-mismatch-note">{opportunityUsageCaption(identity.opportunity_label, model?.usage_trend ?? null)}</p>
        ) : null}
        {/* Beginner-only explanations of the hero's value/OVR/tier labels
            (lib/experienceCopy.ts) — renders nothing for advanced/unset. */}
        {/* One labeled "?" for every term that applies (was three unlabeled
            circles when collapsed). */}
        <BeginnerHelp
          className="mt-1"
          label={isSim ? "What do Overall and Tier mean?" : "What do Value, Overall and Tier mean?"}
          lines={[
            identity.score != null && !isSim ? BEGINNER_HELP.playerValue : null,
            overallRating != null ? BEGINNER_HELP.overallRating : null,
            identity.tier ? BEGINNER_HELP.playerTier : null,
          ]}
        />

        <ExplorerLeagueProvider leagueId={identity.leagueId}>
          <Tabs
            id="pqv"
            ariaLabel="Player sections"
            tabs={orderPlayerSheetTabs([
              {
                key: "overview",
                label: "Overview",
                render: () => (
                  <>
                    {sim?.overview ?? null}
                    {availability ? <AvailabilityBlock availability={availability} injuryItem={news?.injury_item ?? null} newsLoading={newsLoading} /> : null}
                    {!loadError && remote && realWorld.showNews ? (
                      <LatestNewsSection
                        items={news ? news.items : null}
                        hideItem={availability ? news?.injury_item ?? null : null}
                        loading={newsLoading}
                        playerId={identity.player_id}
                        name={name}
                        seeAllHref={identity.leagueId ? playerProfileNewsHref(identity.leagueId, identity.player_id, identity.leagueName || "") : undefined}
                      />
                    ) : null}
                    <div className="pqv-body">
                      {bodyGate ?? (
                        <>
                          {model?.decision_fit_narrative ? <DecisionFitCard narrative={model.decision_fit_narrative} /> : null}
                          <HeadlineTiles rows={headlineRows(stats ?? null, model?.usage_profile)} playerId={identity.player_id} />
                        </>
                      )}
                    </div>
                  </>
                ),
              },
              ...(sim?.outlook || (remote && !isSim)
                ? [
                    {
                      key: "outlook",
                      label: "Outlook",
                      render: () => (
                        <div className="pqv-body">
                          {sim?.outlook ?? null}
                          {!isSim ? (bodyGate ?? <PlayerTrendsPanel playerId={identity.player_id} name={identity.name || "This player"} gradientId="pqv-weekly-fill" />) : null}
                        </div>
                      ),
                    },
                  ]
                : []),
              ...(remote
                ? [
                    {
                      key: "stats",
                      label: "Stats",
                      render: () => (
                        <div className="pqv-body">
                          {sim?.stats ?? null}
                          {bodyGate ?? (
                            <>
                              <PlayerUsageBlock profile={model?.usage_profile} position={stats?.position ?? identity.position} playerId={identity.player_id} />
                              <SeasonStatsRows stats={stats ?? null} usageProfile={model?.usage_profile} playerId={identity.player_id} />
                              {stats && stats.college.length > 0 ? (
                                <section className="pqv-stat-season">
                                  <h3>College</h3>
                                  <StatGroup title="College Stats" items={stats.college} hideTitle />
                                </section>
                              ) : null}
                            </>
                          )}
                        </div>
                      ),
                    },
                    {
                      key: "profile",
                      label: "Profile",
                      render: () => (
                        <div className="pqv-body">
                          {bodyGate ?? (
                            <>
                              {shownAwards.length > 0 ? <AwardsStrip awards={shownAwards} /> : null}
                              {bio ? <BioGrid bio={pqvBioForContext(bio, isSim)} /> : null}
                            </>
                          )}
                        </div>
                      ),
                    },
                  ]
                : []),
              ...(sim?.scouting ? [{ key: "scouting", label: "Scouting", render: () => <>{sim.scouting}</> }] : []),
              ...(sim?.history ? [{ key: "history", label: "History", render: () => <>{sim.history}</> }] : []),
            ])}
          />
        </ExplorerLeagueProvider>

        {identity.leagueId ? (
          <div className="pqv-actions">
            <PlayerLeagueActions
              leagueId={identity.leagueId}
              leagueName={identity.leagueName || ""}
              playerId={identity.player_id}
              sourceSurface="player_quick_view"
              hideAddToTrade={(pathname ?? "").startsWith("/trade-analyzer")}
            />
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
export function PqvBodySkeleton() {
  return (
    <>
      <div aria-hidden="true">
        <div className="pqv-skeleton-section">
          <SkeletonBlock height="0.7rem" />
          <SkeletonBlock width="70%" height="0.7rem" />
        </div>
        <div className="pqv-skeleton-section">
          <SkeletonBlock width="35%" height="0.6rem" />
          <SkeletonBlock height={CHART_HEIGHT} />
        </div>
        {["Production", "Fantasy", "Usage"].map((group) => (
          <div className="pqv-skeleton-section" key={group}>
            <SkeletonBlock width="35%" height="0.6rem" />
            <div className="pqv-stat-grid">
              {Array.from({ length: 6 }, (_, index) => (
                <div key={index} className="pqv-stat-row pqv-skeleton-tile">
                  <SkeletonBlock width="45%" height="0.65rem" />
                  <SkeletonBlock width="70%" height="0.65rem" />
                </div>
              ))}
            </div>
          </div>
        ))}
        <div className="pqv-skeleton-section">
          <SkeletonBlock width="35%" height="0.6rem" />
          <div className="pqv-skeleton-chip-row">
            {Array.from({ length: 5 }, (_, index) => (
              <SkeletonBlock key={index} width="4.5rem" height="1.6rem" />
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
  playerId,
}: {
  title: string;
  items: { label: string; value: string; note: string; percentile: number | null }[];
  hideTitle?: boolean;
  /** When set, tiles that carry a percentile open the Percentile Explorer. */
  playerId?: string;
}) {
  const [explorer, setExplorer] = useState<{ key: string; label: string } | null>(null);
  const { openPlayer } = usePlayerQuickView();
  if (items.length === 0) return null;
  return (
    <div className="pqv-stat-group">
      {hideTitle ? null : <h4>{title}</h4>}
      <div className="pqv-stat-grid">
        {items.map((item) => {
          const statKey = playerId && item.percentile != null ? explorerStatKey(item.label) : null;
          const content = (
            <>
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
            </>
          );
          return statKey ? (
            <button
              key={item.label}
              type="button"
              className="pqv-stat-row pqv-stat-row--tap"
              aria-label={`${item.label} percentile explorer`}
              onClick={() => setExplorer({ key: statKey, label: item.label })}
            >
              {content}
            </button>
          ) : (
            <div key={item.label} className="pqv-stat-row">
              {content}
            </div>
          );
        })}
      </div>
      {explorer && playerId ? (
        <PercentileExplorerSheet
          playerId={playerId}
          statKey={explorer.key}
          statLabel={explorer.label}
          onClose={() => setExplorer(null)}
          onOpenPlayer={(player) => {
            setExplorer(null);
            openPlayer({ ...player, sourceLabel: "Percentile Explorer" });
          }}
        />
      ) : null}
    </div>
  );
}

/** Exported for the full Player Profile page's Model tab — same
 * chip-row/radar-chart renderer, not a second copy. */
export function SubRatingRow({
  model,
  bare = false,
}: {
  /** Drop the "Model" heading (used inside the tap-the-OVR popover, which has its own title). */
  bare?: boolean;
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
    <section className={bare ? "flex flex-col gap-2" : "pqv-model-row"} aria-label="Model sub-ratings">
      {bare ? null : <h3>Model</h3>}
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
