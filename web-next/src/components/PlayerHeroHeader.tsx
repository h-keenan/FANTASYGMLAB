import type { CSSProperties } from "react";

import type { UsageTrend } from "@/lib/api";
import { OvrGauge } from "@/components/OvrGauge";
import { PlayerAvatar } from "@/components/PlayerAvatar";
import { ToneBadge } from "@/components/ToneBadge";
import { PositionBadge } from "@/components/PositionBadge";
import { formatRank, formatScore } from "@/lib/leagueRankingsPresentation";
import { resolvePlayerTier } from "@/lib/playerTier";
import { sentenceCase, usageConfidenceBars, usageTrendTone } from "@/lib/playerQuickViewPresentation";

type ArchetypeStyle = CSSProperties & { "--archetype-color"?: string };

/**
 * The player header shared by Player Quick View and the full Player
 * Profile page. Owner concept, 2026-10-21 ("closer to what I want"):
 * context label top-left level with a round X, a larger name, team and age
 * in a bordered pill beside the position badge, three equal stat tiles
 * (player score ring, value, usage trend with its confidence inside), and
 * the archetype as a rounded pill under a softly glowing headshot.
 *
 * Every value degrades on its own: no rating, no value or no usage read
 * shows a dash in that tile instead of dropping the tile, so the row never
 * reflows; a long name wraps to two lines instead of truncating.
 */
export function PlayerHeroHeader({
  playerId,
  name,
  nameId,
  headingLevel = 2,
  contextLabel,
  position,
  team,
  age,
  tier,
  score,
  overallRating,
  overallRank,
  positionRank,
  usageTrend,
  usageLoading = false,
  depthChartNote,
  valueNote,
  loadingIdentity = false,
  byeWeek = null,
  onByeThisWeek = false,
}: {
  /** Team bye week (null when unknown / free agent). */
  byeWeek?: number | null;
  /** True when the current NFL week is that bye. */
  onByeThisWeek?: boolean;
  /** Why the Value tile is empty (server-provided), e.g. "No market value yet". */
  valueNote?: string | null;
  /** True while server-resolved identity may still fill team/value. */
  loadingIdentity?: boolean;
  playerId: string;
  name: string;
  nameId: string;
  headingLevel?: 1 | 2;
  contextLabel?: string | null;
  position?: string | null;
  team?: string | null;
  age?: number | null;
  tier?: string | null;
  score?: number | null;
  overallRating: number | null;
  overallRank?: number | null;
  positionRank?: number | null;
  usageTrend: UsageTrend | null;
  /** True while the quick-view detail (which carries the usage read) is
   * still loading, so the tile shows a placeholder, not "no trend". */
  usageLoading?: boolean;
  depthChartNote?: string | null;
}) {
  const Heading = headingLevel === 1 ? "h1" : "h2";
  const tierIdentity = tier ? resolvePlayerTier(tier) : null;
  const rankBits = [
    overallRank ? `Overall ${formatRank(overallRank)}` : null,
    positionRank ? `${position || "Position"} ${formatRank(positionRank)}` : null,
  ].filter(Boolean);

  return (
    <div className="pqv-hero-shell">
      <div className="pqv-topbar">
        {contextLabel ? <span className="pqv-source-label">{contextLabel}</span> : null}
      </div>
      <header className="pqv-hero">
        <div className="pqv-hero-avatar-col">
          <span className="pqv-avatar-glow">
            <PlayerAvatar playerId={playerId} tier={tier} size={112} />
          </span>
          {tier ? (
            <span
              className="pqv-archetype-pill"
              style={{ "--archetype-color": tierIdentity ? `var(${tierIdentity.colorVar})` : undefined } as ArchetypeStyle}
            >
              <PersonGlyph />
              {tier}
            </span>
          ) : null}
        </div>

        <div className="pqv-hero-copy">
          <Heading id={nameId} className="pqv-name" title={name}>
            {name}
          </Heading>
          <div className="pqv-meta">
            <PositionBadge position={position} />
            <span className="pqv-meta-pill">
              <span>{team || (loadingIdentity ? "—" : "FA")}</span>
              <span aria-hidden="true">•</span>
              <span>Age {age ?? (loadingIdentity ? "—" : "N/A")}</span>
            </span>
            {byeWeek != null ? (
              <span className="pqv-meta-pill" data-testid="pqv-bye-pill">
                Bye: Wk {byeWeek}
              </span>
            ) : null}
            {byeWeek != null && onByeThisWeek ? (
              <ToneBadge label="On bye this week" color="var(--color-warning)" />
            ) : null}
          </div>
        </div>

        <div className="pqv-stat-tiles">
          <div className="pqv-stat-tile">
            {overallRating != null ? (
              <OvrGauge rating={overallRating} size="lg" />
            ) : (
              <span className="pqv-stat-tile-value pqv-stat-tile-value--empty">—</span>
            )}
            <span className="pqv-stat-tile-caption">Player score</span>
          </div>
          <div className="pqv-stat-tile">
            <span className="pqv-stat-tile-caption">Value</span>
            <span className={`pqv-stat-tile-value${score != null ? "" : " pqv-stat-tile-value--empty"}`}>
              {score != null ? formatScore(score) : "—"}
            </span>
            {score == null && !loadingIdentity ? (
              <span className="pqv-stat-tile-caption">{valueNote || "No market value yet"}</span>
            ) : null}
          </div>
          <UsageTile trend={usageTrend} loading={usageLoading} />
        </div>

        {rankBits.length > 0 || depthChartNote ? (
          <div className="pqv-hero-footnote">
            {rankBits.length > 0 ? <p className="pqv-rank-line">{rankBits.join(" · ")}</p> : null}
            {/* coridian_, 2026-10-19: a depth-chart move is a leading
                indicator games-played/injury signals can't catch. */}
            {depthChartNote ? <p className="pqv-tier-mismatch-note">{depthChartNote}</p> : null}
          </div>
        ) : null}
      </header>
    </div>
  );
}

function UsageTile({ trend, loading }: { trend: UsageTrend | null; loading: boolean }) {
  if (!trend) {
    return (
      <div className="pqv-stat-tile" aria-busy={loading || undefined}>
        {loading ? (
          <span className="pqv-skeleton-line pqv-skeleton-line--short" aria-hidden="true" />
        ) : (
          <span className="pqv-stat-tile-value pqv-stat-tile-value--empty">—</span>
        )}
        <span className="pqv-stat-tile-caption">Usage</span>
        {loading ? null : <span className="pqv-stat-tile-note">No clear trend</span>}
      </div>
    );
  }
  // Same tone everywhere the trend reads: green rising, red for a
  // confirmed decline, neutral for a mild one (usageTrendTone).
  const tone = usageTrendTone(trend);
  const magnitude = Math.abs(trend.trend_pct);
  const confidence = sentenceCase(trend.confidence_label);
  const directionWord = trend.direction === "up" ? "up" : "down";
  return (
    <div
      className={`pqv-stat-tile pqv-stat-tile--usage pqv-stat-tile--${tone}`}
      title={trend.detail}
      aria-label={`Usage ${directionWord} ${magnitude}%, ${confidence.toLowerCase()}`}
      data-testid="pqv-usage-tile"
      data-tone={tone}
    >
      <span className="pqv-stat-tile-value pqv-stat-tile-trend" aria-hidden="true">
        {trend.arrow} {magnitude}%
      </span>
      <span className="pqv-stat-tile-caption" aria-hidden="true">
        Usage
      </span>
      <span className="pqv-stat-tile-divider" aria-hidden="true" />
      <span className="pqv-stat-tile-confidence" aria-hidden="true">
        <SignalBars lit={usageConfidenceBars(trend.confidence_label)} />
        {confidence}
      </span>
    </div>
  );
}

function SignalBars({ lit }: { lit: 1 | 2 | 3 }) {
  return (
    <svg className="pqv-signal-bars" width="14" height="12" viewBox="0 0 14 12" aria-hidden="true">
      {[0, 1, 2].map((index) => (
        <rect
          key={index}
          x={index * 5}
          y={8 - index * 4}
          width="3.2"
          height={4 + index * 4}
          rx="1"
          fill="currentColor"
          opacity={index < lit ? 1 : 0.3}
        />
      ))}
    </svg>
  );
}

function PersonGlyph() {
  return (
    <svg className="pqv-archetype-glyph" width="14" height="14" viewBox="0 0 16 16" aria-hidden="true">
      <circle cx="8" cy="5" r="3" fill="currentColor" />
      <path d="M2.5 14c0-3 2.5-5 5.5-5s5.5 2 5.5 5z" fill="currentColor" />
    </svg>
  );
}

function InsightGlyph() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
      <rect x="2.5" y="9" width="3" height="6.5" rx="1" fill="currentColor" />
      <rect x="7.5" y="5.5" width="3" height="10" rx="1" fill="currentColor" />
      <rect x="12.5" y="2.5" width="3" height="13" rx="1" fill="currentColor" />
    </svg>
  );
}

/** Decision Fit as its own card: icon on the left, accent label, then the
 * backend's one-sentence narrative. Shared by PQV and Player Profile. */
export function DecisionFitCard({ narrative }: { narrative: string }) {
  return (
    <section className="pqv-decision-fit">
      <span className="pqv-decision-fit-icon">
        <InsightGlyph />
      </span>
      <div className="pqv-decision-fit-copy">
        <h3>Decision Fit</h3>
        <p>{narrative}</p>
      </div>
    </section>
  );
}
