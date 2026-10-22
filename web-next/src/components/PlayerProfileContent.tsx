"use client";

import { useEffect, useState } from "react";

import {
  api,
  type PlayerAward,
  type QuickViewResponse,
  type QuickViewStats,
  type RankedPlayer,
} from "@/lib/api";
import { AwardsStrip, BioGrid, StatGroup, SubRatingRow } from "@/components/PlayerQuickView";
import { OvrGauge } from "@/components/OvrGauge";
import { PillRow } from "@/components/PillRow";
import { PlayerAvatar } from "@/components/PlayerAvatar";
import { PlayerCareerTab } from "@/components/PlayerCareerTab";
import { PlayerScheduleTab } from "@/components/PlayerScheduleTab";
import { PlayerTrendsPanel } from "@/components/PlayerTrendsPanel";
import { PositionBadge } from "@/components/PositionBadge";
import { formatRank, formatScore } from "@/lib/leagueRankingsPresentation";
import { resolvePlayerTier } from "@/lib/playerTier";
import { waiverInjuryDisplay } from "@/lib/waiversPresentation";
import { seasonStatGroups, tierOpportunityMismatchCaption } from "@/lib/playerQuickViewPresentation";
import { ValuesCredit } from "@/components/ValuesCredit";
import { BRAND_NAME } from "@/lib/brand";
import { shareImageOrText } from "@/lib/shareImage";

/**
 * Player Profile — the real, full "Open Profile" destination
 * PlayerQuickView.tsx's own header doc comment flags as never built (the
 * "PQV parity gap" in docs/roadmap.md): coridian_, 2026-10-19, "the pqv on
 * the app has tabs that the site doesnt. Thats a consistency error". Ports
 * mobile's PlayerDetailScreen.tsx's 5-tab layout (Stats/Trends/Schedule/
 * Career/Model, see its own `TABS` constant) to a real page rather than a
 * second modal — reached via the "Open Full Profile" link PlayerQuickView's
 * actions row now carries.
 *
 * Identity (name/team/position/tier/rank/...) is NOT part of GET
 * .../quick-view's response (that endpoint is league-independent — see
 * QuickViewResponse's own docstring in lib/api.ts), so the caller resolves
 * it the same way PlayerCompare's route already does: from this league's
 * own GET .../rankings pool (see players/[leagueId]/[playerId]/page.tsx),
 * not a new identity endpoint.
 *
 * Awards and Bio render tab-agnostically, below the tab content — same
 * "always visible, not worth a sixth tab" treatment mobile's own screen
 * gives them (see PlayerDetailScreen.tsx's own comment on its
 * awards-bio-row).
 */

type ProfileTab = "stats" | "trends" | "schedule" | "career" | "model";

const PROFILE_TABS: Array<{ label: string; value: ProfileTab }> = [
  { label: "Stats", value: "stats" },
  { label: "Trends", value: "trends" },
  { label: "Schedule", value: "schedule" },
  { label: "Career", value: "career" },
  { label: "Model", value: "model" },
];

function StatsTab({ stats }: { stats: QuickViewStats | null }) {
  if (!stats || (stats.seasons.length === 0 && stats.college.length === 0)) {
    return <p className="pqv-status-text">No stats available for this player yet.</p>;
  }
  return (
    <>
      {stats.seasons.map((season) => (
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
      {stats.college.length > 0 ? (
        <section className="pqv-stat-season">
          <h3>College</h3>
          <StatGroup title="College Stats" items={stats.college} hideTitle />
        </section>
      ) : null}
    </>
  );
}

/** Shares the branded player card PNG (app/share-card/player) through the
 * same image -> text -> clipboard flow as Trade Hub's Share button. */
function SharePlayerButton({ player, leagueId, lens }: { player: RankedPlayer; leagueId: string; lens: string }) {
  const [preparing, setPreparing] = useState(false);
  const [copied, setCopied] = useState(false);
  const name = player.name || `Player ${player.player_id}`;

  const onShare = async () => {
    const facts = [
      player.position && player.position_rank ? `${player.position}${player.position_rank}` : player.position,
      player.overall_rank ? `#${player.overall_rank} overall` : null,
      player.score != null ? `${formatScore(player.score)} value` : null,
    ].filter(Boolean);
    const outcome = await shareImageOrText({
      fetchImage: () => api.getPlayerShareCardBlob(leagueId, player.player_id, lens),
      filename: `fantasydesk-player-${player.player_id}.png`,
      text: `${name}${facts.length ? ` · ${facts.join(" · ")}` : ""} on ${BRAND_NAME}`,
      title: `${name} on ${BRAND_NAME}`,
      onPreparingImage: setPreparing,
    });
    if (outcome === "copied") {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <button type="button" className="pqv-action-link" onClick={onShare} disabled={preparing}>
      {preparing ? "Preparing…" : copied ? "Copied!" : "Share card"}
    </button>
  );
}

export function PlayerProfileContent({
  player,
  leagueId,
  leagueName,
  lens = "Dynasty",
}: {
  player: RankedPlayer;
  leagueId: string;
  leagueName: string;
  /** The valuation lens the page's rankings were loaded under, so the
   * share card shows the same value. */
  lens?: string;
}) {
  const [detail, setDetail] = useState<QuickViewResponse | null>(null);
  const [awards, setAwards] = useState<PlayerAward[]>([]);
  const [loadError, setLoadError] = useState(false);
  const [tab, setTab] = useState<ProfileTab>("stats");
  // Which player `detail`/`awards` actually belong to — compared against
  // player.player_id below to derive "still loading" without a second
  // setState call synchronously at the top of the effect (same
  // derive-instead-of-reset pattern as PlayerCompareContent.tsx's own
  // modelsLoadedFor).
  const [loadedFor, setLoadedFor] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    Promise.all([api.getPlayerQuickView(player.player_id), api.getPlayerAwards(player.player_id)])
      .then(([quickView, awardsResponse]) => {
        if (cancelled) return;
        setDetail(quickView);
        setAwards(awardsResponse.ok ? awardsResponse.awards : []);
        setLoadError(false);
      })
      .catch(() => {
        if (cancelled) return;
        setLoadError(true);
      })
      .finally(() => {
        if (!cancelled) setLoadedFor(player.player_id);
      });

    return () => {
      cancelled = true;
    };
  }, [player.player_id]);

  const loading = loadedFor !== player.player_id;
  const stats = detail?.stats ?? null;
  const bio = detail?.bio ?? null;
  const model = detail?.model ?? null;
  const injury = waiverInjuryDisplay(player.injury_status);
  const overallRating = player.overall_rating ?? stats?.overall_rating ?? null;
  const name = player.name || `Player ${player.player_id}`;

  return (
    <main className="flex-1 flex flex-col gap-6 px-4 py-8 max-w-3xl w-full mx-auto">
      <header className="pqv-hero">
        <div className="pqv-hero-avatar-col">
          <PlayerAvatar playerId={player.player_id} tier={player.tier} size={112} />
          {player.tier ? (
            <span
              className="pqv-chip pqv-tier-chip"
              style={{
                borderColor: `var(${resolvePlayerTier(player.tier).colorVar})`,
                color: `var(${resolvePlayerTier(player.tier).colorVar})`,
              }}
            >
              {player.tier}
            </span>
          ) : null}
        </div>
        <div className="pqv-hero-copy">
          <span className="pqv-source-label">{leagueName}</span>
          <h1 id="profile-name" className="pqv-name" style={{ font: "var(--font-page-title)" }}>
            {name}
          </h1>
          <div className="pqv-meta">
            <PositionBadge position={player.position} />
            <span>{player.team || "FA"}</span>
            <span>·</span>
            <span>Age {player.age ?? "N/A"}</span>
          </div>
          <div className="pqv-rank-strip">
            <OvrGauge rating={overallRating} size="lg" />
            <div className="pqv-rank-cells">
              {player.score != null ? (
                <div className="pqv-rank-cell">
                  <span>Value</span>
                  <strong>{formatScore(player.score)}</strong>
                </div>
              ) : null}
              {player.overall_rank ? (
                <div className="pqv-rank-cell">
                  <span>Overall rank</span>
                  <strong>{formatRank(player.overall_rank)}</strong>
                </div>
              ) : null}
              {player.position_rank ? (
                <div className="pqv-rank-cell">
                  <span>Position rank</span>
                  <strong>
                    {player.position || ""}
                    {player.position_rank}
                  </strong>
                </div>
              ) : null}
            </div>
          </div>
          {model?.usage_trend ? (
            <span
              className={`pqv-chip pqv-chip--${model.usage_trend.tone === "positive" ? "positive" : "danger"}`}
              title={model.usage_trend.detail}
            >
              {model.usage_trend.arrow} {model.usage_trend.trend_pct}% usage · {model.usage_trend.confidence_label}
            </span>
          ) : null}
          {model?.depth_chart_note ? <p className="pqv-tier-mismatch-note">{model.depth_chart_note}</p> : null}
        </div>
      </header>

      <div className="pqv-signal-row">
        {player.opportunity_label ? <span className="pqv-chip">{player.opportunity_label}</span> : null}
        {injury.label ? <span className={`pqv-chip pqv-chip--${injury.tone}`}>Health: {injury.label}</span> : null}
      </div>
      {tierOpportunityMismatchCaption(player.tier, player.opportunity_label) ? (
        <p className="pqv-tier-mismatch-note">
          {tierOpportunityMismatchCaption(player.tier, player.opportunity_label)}
        </p>
      ) : null}

      <div className="pqv-body">
        {loading ? (
          <p className="pqv-status-text">Loading player profile…</p>
        ) : loadError ? (
          <p className="pqv-status-text" role="alert">
            Couldn&apos;t load this player&apos;s profile right now.
          </p>
        ) : (
          <>
            {model?.decision_fit_narrative ? (
              <section className="pqv-decision-fit">
                <h3>Decision Fit</h3>
                <p>{model.decision_fit_narrative}</p>
              </section>
            ) : null}

            <PillRow
              options={PROFILE_TABS.map((option) => ({ label: option.label, value: option.value }))}
              active={tab}
              onSelect={(value) => setTab(value as ProfileTab)}
            />

            <div className="flex flex-col gap-4">
              {tab === "stats" ? <StatsTab stats={stats} /> : null}
              {tab === "trends" ? (
                <PlayerTrendsPanel playerId={player.player_id} name={name} gradientId="profile-weekly-fill" />
              ) : null}
              {tab === "schedule" ? <PlayerScheduleTab playerId={player.player_id} /> : null}
              {tab === "career" ? <PlayerCareerTab playerId={player.player_id} /> : null}
              {tab === "model" ? (
                model ? (
                  <SubRatingRow model={model} />
                ) : (
                  <p className="pqv-status-text">No model breakdown available for this player yet.</p>
                )
              ) : null}
            </div>

            {awards.length > 0 ? <AwardsStrip awards={awards} /> : null}
            {bio ? <BioGrid bio={bio} /> : null}
          </>
        )}
      </div>

      <div className="pqv-actions">
        <SharePlayerButton player={player} leagueId={leagueId} lens={lens} />
        <a
          className="pqv-action-link"
          href={`/player-compare/${encodeURIComponent(leagueId)}?a=${encodeURIComponent(player.player_id)}&name=${encodeURIComponent(leagueName)}`}
        >
          Compare this player
        </a>
      </div>
      <ValuesCredit />
    </main>
  );
}
