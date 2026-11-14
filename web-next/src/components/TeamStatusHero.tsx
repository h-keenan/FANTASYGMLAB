"use client";

import { InsightLink } from "@/components/ui/InsightLink";
import Link from "next/link";
import { useEffect, useState } from "react";
import { SkeletonCard } from "@/components/Skeleton";

import { CompactModule } from "@/components/ui/CompactModule";
import { Hero, LinkModule } from "@/components/ui/ModuleTemplates";
import { lineupModuleParts, roomsModuleParts, standingModuleParts, teamStatusHeroModel } from "@/lib/teamStatusModules";
import { SectionHeading } from "@/components/SectionHeading";
import { TeamAvatar } from "@/components/TeamAvatar";
import { ToneBadge } from "@/components/ToneBadge";
import { api, type GamesSeasonSimResponse, type LeagueTeamRankingsResponse, type MatchupResponse, type MyTeamNeedsResponse, type TeamSnapshot } from "@/lib/api";
import {
  buildTeamStatusLineup,
  buildTeamStatusMatchup,
  buildTeamStatusOdds,
  buildTeamStatusPositions,
  buildTeamStatusStanding,
  type TeamStatusPosition,
} from "@/lib/teamStatus";

const TONE_COLOR = {
  positive: "var(--color-success)",
  risk: "var(--color-danger)",
  warning: "var(--color-warning)",
  neutral: "var(--color-text-primary)",
} as const;

/** The three reads the hero needs beyond the Dashboard payload. Each failing just hides its row. */
export function useTeamStatusData(
  leagueId: string,
  lens: string,
  enabled: boolean,
  teamRankings?: Promise<LeagueTeamRankingsResponse>,
  /** Requests the page already started (alongside the Dashboard call), so the
   * hero does not wait a full Dashboard round trip before asking for them. */
  prefetch?: TeamStatusPrefetch,
) {
  const [matchup, setMatchup] = useState<MatchupResponse | null>(null);
  const [needs, setNeeds] = useState<MyTeamNeedsResponse | null>(null);
  const [rankings, setRankings] = useState<LeagueTeamRankingsResponse | null>(null);
  // True once all three reads have landed or failed; until then the hero holds
  // its place with a skeleton instead of popping in and pushing the page down.
  const [settled, setSettled] = useState(!enabled);
  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    const matchupRequest = prefetch?.matchup ?? api.getLeagueMatchup(leagueId, lens);
    const needsRequest = prefetch?.needs ?? api.getMyTeamNeeds(leagueId, lens);
    const rankingsRequest = teamRankings ?? api.getTeamRankings(leagueId, lens);
    const track = <T,>(request: Promise<T>, apply: (value: T) => void) =>
      request
        .then((value) => {
          if (!cancelled) apply(value);
        })
        .catch(() => {});
    void Promise.all([track(matchupRequest, setMatchup), track(needsRequest, setNeeds), track(rankingsRequest, setRankings)]).then(() => {
      if (!cancelled) setSettled(true);
    });
    return () => {
      cancelled = true;
    };
  }, [leagueId, lens, enabled, teamRankings, prefetch]);
  return { matchup, needs, rankings, settled };
}

export type TeamStatusPrefetch = { matchup: Promise<MatchupResponse>; needs: Promise<MyTeamNeedsResponse> };

function Fact({ label, value, tone = "neutral" }: { label: string; value: string; tone?: keyof typeof TONE_COLOR }) {
  return (
    <span className="flex min-w-0 flex-col">
      <span className="text-[0.6875rem] leading-tight" style={{ color: "var(--color-text-muted)" }}>
        {label}
      </span>
      <span className="text-base font-extrabold tabular-nums" style={{ color: TONE_COLOR[tone] }}>
        {value}
      </span>
    </span>
  );
}

function RowLink({ href, label, children }: { href: string; label: string; children: React.ReactNode }) {
  return (
    <Link
      href={href}
      aria-label={label}
      className="flex items-center gap-2 py-2.5 border-t first:border-t-0"
      style={{ minHeight: 44, color: "inherit", textDecoration: "none", borderTopColor: "var(--color-border)" }}
    >
      <span className="min-w-0 flex-1 flex flex-col gap-1">{children}</span>
      <span aria-hidden="true" style={{ color: "var(--color-accent)" }}>
        →
      </span>
    </Link>
  );
}

function PositionChip({ row, league }: { row: TeamStatusPosition; league: { id: string; name: string } }) {
  const color = TONE_COLOR[row.tone];
  return (
    <InsightLink insight="position_room" league={league} spoken={[`${row.position} room`, row.label]} testId={`team-status-position-link-${row.position}`}>
    <span
      className="flex flex-col items-center px-1 py-1.5 min-w-0"
      data-testid={`team-status-position-${row.position}`}
      data-weakest={row.weakest ? "true" : undefined}
      style={{
        borderRadius: "var(--radius-card, 12px)",
        border: `1px solid ${row.weakest ? color : "var(--color-border)"}`,
        background: row.weakest ? `color-mix(in srgb, ${color} 12%, transparent)` : "var(--color-surface-muted)",
      }}
    >
      <span className="text-xs font-extrabold">{row.position}</span>
      <span className="text-[0.6875rem] text-center leading-tight" style={{ color }}>
        {row.label}
      </span>
    </span>
    </InsightLink>
  );
}

/**
 * "Your team right now": this week's matchup, lineup health, season standing and
 * position-room strength in one card, each row linking to the page that owns
 * the detail. Every row is built from data the other pages already show
 * (lib/teamStatus.ts) and is hidden, never zero-filled, when that data is
 * missing (offseason, imported league, request failed).
 */
export function TeamStatusHero({
  leagueId,
  leagueName,
  snapshot,
  sim,
  oddsCaption,
  data,
}: {
  leagueId: string;
  leagueName: string;
  snapshot: TeamSnapshot | null;
  sim: GamesSeasonSimResponse | null;
  /** "6 weeks left, 3,000 simulated seasons" under the odds. */
  oddsCaption?: string;
  data: ReturnType<typeof useTeamStatusData>;
}) {
  const query = `?name=${encodeURIComponent(leagueName)}`;
  const id = encodeURIComponent(leagueId);
  const matchupLine = buildTeamStatusMatchup(data.matchup);
  const lineup = buildTeamStatusLineup(data.matchup, snapshot?.injured_starters);
  const standing = buildTeamStatusStanding({
    snapshot,
    rankings: data.rankings?.teams,
    standingsAvailable: data.rankings?.standings_available,
    myRosterId: data.matchup?.my_team?.roster_id,
    odds: buildTeamStatusOdds(sim),
  });
  const positions = buildTeamStatusPositions(data.needs);
  const weakest = positions.find((row) => row.weakest);
  if (!data.settled) {
    return (
      <section className="flex flex-col gap-3" aria-labelledby="team-status-heading" aria-busy="true" data-testid="team-status-hero-loading">
        <SectionHeading id="team-status-heading" size="compact">
          Your team right now
        </SectionHeading>
        {/* Reserve the height a full in-season hero settles at (matchup, lineup,
            standing and position rooms: ~324 px with its heading). A shorter
            placeholder made everything below it jump ~136 px when the data
            landed (dashboard CLS 0.11, measured). */}
        <SkeletonCard lines={5} style={{ minHeight: 290 }} />
      </section>
    );
  }
  if (!matchupLine && !lineup && !standing && positions.length === 0) return null;

  const heroModel = teamStatusHeroModel(matchupLine, standing);
  // No decision twice: when the Hero already IS the standing, the Standing module only appears if it adds odds or a projection.
  const heroIsStanding = heroModel != null && !(matchupLine && (matchupLine.winPercent != null || matchupLine.live));
  const showStanding = standing != null && (!heroIsStanding || Boolean(standing.playoffOdds || standing.projectedRecord || standing.playoffStatus));
  const league = { id: leagueId, name: leagueName };

  return (
    <section className="flex flex-col gap-2" aria-labelledby="team-status-heading" data-testid="team-status-hero">
      <h2 id="team-status-heading" className="sr-only">
        Your team right now
      </h2>
      {/* One Hero (the number that matters this week) then three modules that read while collapsed. */}
      {heroModel ? (
        <Hero
          label={heroModel.label}
          value={heroModel.value}
          context={heroModel.context}
          tone={heroModel.tone}
          href={matchupLine ? `/matchup/${id}${query}` : `/league-rankings/${id}${query}`}
          testId="team-status-main"
        />
      ) : null}

      {lineup ? (
        <LinkModule
          title="Lineup"
          href={`/matchup/${id}${query}`}
          tone={lineup.tone === "risk" ? "danger" : lineup.tone === "positive" ? "success" : "accent"}
          parts={lineupModuleParts(lineup)}
          testId="team-status-lineup"
        />
      ) : null}

      {standing && showStanding ? (
        <CompactModule id="today.standing" title="Standing" tone={standing.tone === "risk" ? "danger" : standing.tone === "positive" ? "success" : "accent"} parts={standingModuleParts(standing)} testId="team-status-standing">
          <Link href={`/league-rankings/${id}${query}`} aria-label="Season standing, open League Rankings" className="flex flex-col gap-2" style={{ color: "inherit", textDecoration: "none" }}>
            <span className="grid grid-cols-4 gap-2">
              {standing.record ? <Fact label="Record" value={standing.record} /> : null}
              {standing.place ? <Fact label="Standing" value={standing.place} /> : null}
              {standing.playoffOdds ? <Fact label="Playoff odds" value={standing.playoffOdds} tone={standing.tone === "neutral" ? "neutral" : standing.tone} /> : null}
              {standing.projectedRecord ? <Fact label="Proj. record" value={standing.projectedRecord} /> : null}
            </span>
            {standing.playoffOdds && oddsCaption ? (
              <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                Odds from a rest-of-season simulation: {oddsCaption}.
              </span>
            ) : null}
            {standing.playoffStatus ? (
              <span className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
                {standing.playoffStatus}
              </span>
            ) : null}
            <span className="text-xs font-bold" style={{ color: "var(--color-accent)" }}>
              Open League Rankings →
            </span>
          </Link>
        </CompactModule>
      ) : null}

      {positions.length > 0 ? (
        <CompactModule id="today.rooms" title="Position rooms" tone={weakest ? "warning" : "accent"} parts={roomsModuleParts(positions)} testId="team-status-positions">
          <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
            Position rooms vs the league. Tap a room for the detail ›
          </span>
          <span className="grid grid-cols-4 gap-2">
            {positions.map((row) => (
              <PositionChip key={row.position} row={row} league={league} />
            ))}
          </span>
          {weakest ? (
            <Link href={`/trade-hub/${id}${query}`} className="text-xs font-bold" style={{ color: "var(--color-accent)", textDecoration: "none" }}>
              Improve {weakest.position} first: see Trade Hub ideas →
            </Link>
          ) : null}
        </CompactModule>
      ) : null}
    </section>
  );
}
