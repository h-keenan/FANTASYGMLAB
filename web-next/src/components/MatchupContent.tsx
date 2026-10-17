import type { ReactNode } from "react";
import type { MatchupRealStarter, MatchupResponse, MatchupSide, MatchupStarter } from "@/lib/api";
import { OvrGauge } from "@/components/OvrGauge";
import { PlayerAvatar } from "@/components/PlayerAvatar";
import { PlayerIdentityTrigger } from "@/components/PlayerIdentityTrigger";
import { PositionBadge } from "@/components/PositionBadge";
import { TeamAvatar } from "@/components/TeamAvatar";
import { injuryTone } from "@/lib/myTeamPresentation";
import { leanBar } from "@/lib/tradeHubPresentation";
import {
  deriveContextLine,
  formatSeasonValue,
  matchupReasonMessage,
  realStarterPointsDisplay,
  recordLabel,
} from "@/lib/matchupPresentation";

/**
 * Ports modules/web_matchup_ui.py's render_matchup_page for Revision 5 — the
 * real Streamlit Matchup page's own section order: hero verdict, each
 * side's REAL current-week lineup (only once Sleeper has it), the
 * suggested-lineup disclosure, then each side's suggested best lineup.
 * Backed by the same GET .../leagues/{id}/matchup mobile's MatchupScreen.tsx
 * already uses — this page and mobile can never disagree about what "this
 * week's real matchup" means, since both read the one endpoint.
 *
 * Deliberately NOT ported from mobile: the client-side "Injury Watch"
 * roll-up section. That's a mobile-only presentation grouping of starters
 * already visible on both lineups below (not a distinct ground-truth
 * section of the real Streamlit page this revision ports) — each injured
 * starter still surfaces, in place, on its own lineup row here via the same
 * injury pill My Team uses.
 */

function SectionHeading({ children }: { children: ReactNode }) {
  return (
    <h2 className="uppercase" style={{ font: "var(--type-section-title)", letterSpacing: "0.02em" }}>
      {children}
    </h2>
  );
}

function edgeColor(edge: "you" | "opponent" | "even"): string {
  if (edge === "you") return "var(--color-success)";
  if (edge === "opponent") return "var(--color-danger)";
  return "var(--color-text-muted)";
}

function VersusSide({
  side,
  value,
  subValue,
  highlighted,
}: {
  side: MatchupSide;
  value: string;
  subValue: string | null;
  highlighted: boolean;
}) {
  return (
    <div className="flex-1 flex flex-col items-center text-center gap-0.5 min-w-0">
      <TeamAvatar avatarUrl={side.avatar_url} size={40} ringColor={highlighted ? "var(--color-accent)" : "var(--color-border)"} />
      <span className="text-sm font-bold truncate w-full" style={{ color: "var(--color-text-primary)" }}>
        {side.team_name}
      </span>
      <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
        {recordLabel(side)}
      </span>
      <span
        style={{
          font: "var(--type-primary-metric)",
          color: highlighted ? "var(--color-accent)" : "var(--color-text-primary)",
          marginTop: "var(--space-xs)",
        }}
      >
        {value}
      </span>
      {subValue ? (
        <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          {subValue}
        </span>
      ) : null}
    </div>
  );
}

function MatchupHero({ matchup }: { matchup: MatchupResponse }) {
  const mine = matchup.my_team as MatchupSide;
  const opponent = matchup.opponent as MatchupSide;
  const comparison = matchup.comparison!;
  const realComparison = matchup.real_comparison;
  const week = matchup.week;

  const myValue = realComparison ? realComparison.my_points.toFixed(1) : formatSeasonValue(comparison.my_season_value);
  const opponentValue = realComparison
    ? realComparison.opponent_points.toFixed(1)
    : formatSeasonValue(comparison.opponent_season_value);
  const mySub = realComparison ? `${formatSeasonValue(comparison.my_season_value)} season value` : null;
  const opponentSub = realComparison ? `${formatSeasonValue(comparison.opponent_season_value)} season value` : null;

  const edge = realComparison ? realComparison.edge : comparison.edge;
  let headline = realComparison
    ? realComparison.edge === "you"
      ? "You're ahead on live points"
      : realComparison.edge === "opponent"
        ? "Your opponent is ahead on live points"
        : "It's tied on live points right now"
    : comparison.headline;
  if (edge !== "even") {
    const margin = realComparison ? realComparison.margin : comparison.margin;
    const rounded = realComparison ? margin.toFixed(1) : formatSeasonValue(margin).toString();
    headline += ` (${margin > 0 ? "+" : ""}${rounded})`;
  }
  const basisLabel = realComparison ? realComparison.basis_label : comparison.basis_label;
  const secondary =
    realComparison && comparison.headline
      ? `By season value: ${comparison.headline}${
          comparison.edge === "even" ? "" : ` (${comparison.margin > 0 ? "+" : ""}${formatSeasonValue(comparison.margin)})`
        }`
      : null;

  // "need team pfp and a bar saying whos winnig/ projected to win" —
  // coridian_, 2026-10-17. The API has no win-probability field (see
  // MatchupComparison/MatchupRealComparison in api.ts), so this is a current
  // value/points lean, not a fabricated probability — reuses the same
  // leanBar() math + .lean-bar-* CSS Trade Hub/Analyzer already ship,
  // fed by the exact two numbers already shown above (myValue/opponentValue).
  const myLeanScore = realComparison ? realComparison.my_points : comparison.my_season_value;
  const opponentLeanScore = realComparison ? realComparison.opponent_points : comparison.opponent_season_value;
  // leanBar's "pos" (green) fires when the second arg exceeds the first, so
  // opponent goes first here — "pos" means I'm ahead, matching the
  // success/danger color sense everywhere else in this app.
  const { polarity: leanPolarity, halfTrackPercent } = leanBar(opponentLeanScore, myLeanScore);
  const leanLabel = `${realComparison ? "Live points" : "Season value"} lean: you ${myLeanScore.toFixed(
    1,
  )}, opponent ${opponentLeanScore.toFixed(1)}.`;

  return (
    <div
      className="flex flex-col gap-3 p-4"
      style={{
        background: "var(--color-surface-raised)",
        border: "var(--border-width-default) solid var(--color-border)",
        boxShadow: "var(--shadow-card)",
      }}
    >
      <div className="flex items-center gap-2">
        <span
          className="uppercase font-extrabold"
          style={{ font: "var(--type-supporting-metadata)", color: "var(--color-accent)", letterSpacing: "var(--letter-spacing-badge)" }}
        >
          {week != null ? `WEEK ${week}` : "THIS WEEK"}
        </span>
        {realComparison ? (
          <span
            className="px-1.5 uppercase font-extrabold"
            style={{
              background: "var(--color-accent-soft)",
              color: "var(--color-accent)",
              font: "var(--type-supporting-metadata)",
              letterSpacing: "var(--letter-spacing-badge)",
              borderRadius: "var(--radius-pill)",
            }}
          >
            Live
          </span>
        ) : null}
      </div>

      <div className="flex items-start gap-3">
        <VersusSide side={mine} value={myValue} subValue={mySub} highlighted={edge === "you"} />
        <span
          className="text-xs font-extrabold self-center"
          style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}
        >
          VS
        </span>
        <VersusSide side={opponent} value={opponentValue} subValue={opponentSub} highlighted={edge === "opponent"} />
      </div>

      <div className="lean-bar-track" role="img" aria-label={leanLabel}>
        <span className="lean-bar-tick" aria-hidden="true" />
        {halfTrackPercent > 0 ? (
          <span
            className={`lean-bar-fill lean-bar-fill--${leanPolarity}`}
            style={{ width: `${halfTrackPercent}%` }}
            aria-hidden="true"
          />
        ) : null}
      </div>

      <div className="flex flex-col gap-0.5">
        <span className="text-base font-extrabold" style={{ color: edgeColor(edge) }}>
          {headline}
        </span>
        <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          {basisLabel}
        </span>
        {secondary ? (
          <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
            {secondary}
          </span>
        ) : null}
      </div>
    </div>
  );
}

function SuggestedStarterRow({ player }: { player: MatchupStarter }) {
  const tone = injuryTone(player.injury_label);
  const contextLine = deriveContextLine(player);
  return (
    <div
      className="flex items-center gap-3 py-2"
      style={{ borderBottom: "var(--border-width-default) solid var(--color-border)" }}
    >
      <PlayerIdentityTrigger
        identity={{ ...player, sourceLabel: "Matchup" }}
        className="flex-1 flex items-center gap-3 min-w-0"
      >
        <PositionBadge position={player.position} />
        <PlayerAvatar playerId={player.player_id} tier={player.tier} size={40} />
        <div className="flex-1 flex flex-col gap-0.5 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-bold truncate" style={{ color: "var(--color-text-primary)" }}>
              {player.name || "Unknown player"}
            </span>
            {player.injury_label ? (
              <span
                className="px-1 text-xs font-bold uppercase"
                style={{
                  color: tone === "danger" ? "var(--color-danger)" : tone === "warning" ? "var(--color-warning)" : "var(--color-text-muted)",
                }}
              >
                {player.injury_label}
              </span>
            ) : null}
          </div>
          <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
            {contextLine || `${player.team || "FA"}${player.slot ? ` · ${player.slot}` : ""}`}
          </span>
        </div>
      </PlayerIdentityTrigger>
      <div className="flex items-center gap-2 shrink-0">
        <OvrGauge rating={player.overall_rating} size="sm" />
        <div className="flex flex-col items-end gap-0.5">
          <span className="text-sm font-extrabold" style={{ color: "var(--color-accent)" }}>
            {player.score != null ? Math.round(player.score) : "—"}
          </span>
          <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
            VALUE
          </span>
        </div>
      </div>
    </div>
  );
}

function RealStarterRow({ player }: { player: MatchupRealStarter }) {
  const tone = injuryTone(player.injury_label);
  const display = realStarterPointsDisplay(player);
  return (
    <div
      className="flex items-center gap-3 py-2"
      style={{ borderBottom: "var(--border-width-default) solid var(--color-border)" }}
    >
      <PlayerIdentityTrigger
        identity={{ ...player, sourceLabel: "Matchup" }}
        className="flex-1 flex items-center gap-3 min-w-0"
      >
        <PositionBadge position={player.position} />
        <PlayerAvatar playerId={player.player_id} tier={player.tier} size={40} />
        <div className="flex-1 flex flex-col gap-0.5 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-bold truncate" style={{ color: "var(--color-text-primary)" }}>
              {player.name || "Unknown player"}
            </span>
            {player.injury_label ? (
              <span
                className="px-1 text-xs font-bold uppercase"
                style={{
                  color: tone === "danger" ? "var(--color-danger)" : tone === "warning" ? "var(--color-warning)" : "var(--color-text-muted)",
                }}
              >
                {player.injury_label}
              </span>
            ) : null}
          </div>
          <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
            {player.team || "FA"}
          </span>
        </div>
      </PlayerIdentityTrigger>
      <div className="flex items-center gap-2 shrink-0">
        <OvrGauge rating={player.overall_rating} size="sm" />
        <div className="flex flex-col items-end gap-0.5">
          <span className="text-sm font-extrabold" style={{ color: "var(--color-accent)" }}>
            {display.value}
          </span>
          {display.caption ? (
            <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
              {display.caption}
            </span>
          ) : null}
          {display.secondaryValue ? (
            <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
              {display.secondaryValue}
              {display.secondaryCaption ? ` · ${display.secondaryCaption}` : ""}
            </span>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function RealLineupSection({ title, side }: { title: string; side: MatchupSide }) {
  if (!side.has_live_data || side.real_starters.length === 0) return null;
  return (
    <section className="flex flex-col gap-3">
      <div className="flex items-baseline justify-between">
        <SectionHeading>{title}</SectionHeading>
        {side.real_points != null ? (
          <span className="text-xs font-bold" style={{ color: "var(--color-accent)" }}>
            {side.real_points.toFixed(1)} PTS
          </span>
        ) : null}
      </div>
      <div className="flex flex-col" style={{ background: "var(--color-surface-secondary)", border: "var(--border-width-default) solid var(--color-border)" }}>
        {side.real_starters.map((player, index) => (
          <RealStarterRow key={`${side.roster_id}-real-${player.player_id}-${index}`} player={player} />
        ))}
      </div>
    </section>
  );
}

function SuggestedLineupSection({ title, side }: { title: string; side: MatchupSide }) {
  return (
    <section className="flex flex-col gap-3">
      <div className="flex items-baseline justify-between">
        <SectionHeading>{title}</SectionHeading>
        <span className="text-xs font-bold" style={{ color: "var(--color-accent)" }}>
          {formatSeasonValue(side.season_value_total)} SEASON VALUE
        </span>
      </div>
      {side.starters.length === 0 ? (
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
          No startable players on this roster right now.
        </p>
      ) : (
        <div className="flex flex-col" style={{ background: "var(--color-surface-secondary)", border: "var(--border-width-default) solid var(--color-border)" }}>
          {side.starters.map((player) => (
            <SuggestedStarterRow key={player.player_id} player={player} />
          ))}
        </div>
      )}
    </section>
  );
}

export function MatchupContent({ leagueName, matchup }: { leagueName: string; matchup: MatchupResponse }) {
  const notReady = !matchup.ok || !matchup.my_team || !matchup.opponent || !matchup.comparison;
  if (notReady) {
    return (
      <main className="flex-1 flex items-center justify-center px-4">
        <p className="text-sm text-center" style={{ color: "var(--color-text-muted)" }}>
          {matchupReasonMessage(matchup.reason)}
        </p>
      </main>
    );
  }

  const mine = matchup.my_team!;
  const opponent = matchup.opponent!;

  return (
    <main className="flex-1 flex flex-col gap-8 px-4 py-8 max-w-3xl w-full mx-auto">
      <header className="flex flex-col gap-1">
        <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          Matchup
        </span>
        <h1 style={{ font: "var(--font-page-title)" }}>{leagueName}</h1>
      </header>

      <MatchupHero matchup={matchup} />

      <RealLineupSection title="Your actual lineup this week" side={mine} />
      <RealLineupSection title={`${opponent.team_name}'s actual lineup`} side={opponent} />

      <p
        className="text-sm p-4"
        style={{ background: "var(--color-surface-secondary)", border: "var(--border-width-default) solid var(--color-border)", color: "var(--color-text-secondary)" }}
      >
        The suggested starters below are each roster&apos;s best available lineup by season-long value — the same
        optimal-lineup logic My Team uses, run for your opponent too so the comparison is apples to apples. This is a
        recommendation, not necessarily the lineup either manager has actually set in Sleeper. Weekly projections
        (where shown) come from this player&apos;s own recent-week trend — see each real-lineup row&apos;s projection
        note for the honest range and confidence.
      </p>

      <SuggestedLineupSection title="Your suggested starters" side={mine} />
      <SuggestedLineupSection title={`${opponent.team_name}'s best lineup`} side={opponent} />
    </main>
  );
}
