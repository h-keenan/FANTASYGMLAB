"use client";

import { useState } from "react";

import { BeginnerHelp } from "@/components/BeginnerHelp";
import { api, type LeagueTeamRankingsResponse, type PlayoffOddsResponse, type PlayoffOddsTeam, type TeamRanking } from "@/lib/api";
import {
  boardSecondaryParts,
  formatRank,
  formatScore,
  metricToneColor,
  percentileFromRank,
  playoffOddsReasonMessage,
  RANK_BOARD_CONFIG,
  sortByBoard,
  sortByStanding,
  teamBadgeTone,
  teamRankingsReasonMessage,
  type RankBoardKey,
} from "@/lib/leagueRankingsPresentation";
import { ManagerProfileSheet } from "@/components/ManagerProfileSheet";
import { SectionHeading } from "@/components/SectionHeading";
import { TeamAvatar } from "@/components/TeamAvatar";
import { ToneBadge } from "@/components/ToneBadge";
import { ValuesCredit } from "@/components/ValuesCredit";
import { EmptyState } from "@/components/EmptyState";

/**
 * Ports app.py's "League Rankings" page (current_page == "rankings",
 * forced_league_section == "Rankings" — renamed from "League Overview" by
 * PR #1072, page content untouched by that rename) for Revision 6:
 * Standings, Playoff Odds (gated behind an explicit tap, same Monte Carlo
 * cost boundary the real page preserves), and the five Roster Power /
 * Franchise Value / Draft Capital / Starter Quality / Bench Depth boards.
 * All backed by the one GET .../team-rankings endpoint mobile's
 * TeamsScreen.tsx already uses (extended this revision to also expose the
 * raw scores/standings presentation fields the web boards need — see that
 * endpoint's docstring) plus GET .../playoff-odds for the deferred board.
 *
 * Deliberately NOT ported this revision: the "League Insights" decision-
 * card/leader-card band and the New-Startup "Post-Draft Roster Read" tiles
 * beneath it, and the "How to read these boards" concept-band disclosure.
 * Those aren't in the task's named board list (Standings/Playoff Odds/
 * Roster Power/Franchise Value/Draft Capital/Starter Quality/Bench Depth)
 * and would need a new decision-cards endpoint beyond team-rankings, not a
 * thin wrapper — left for a future revision rather than guessed at here.
 */

function rankBadgeColor(tone: "positive" | "negative" | "neutral" = "neutral"): string {
  return tone === "positive" ? "var(--color-success)" : tone === "negative" ? "var(--color-danger)" : "var(--color-text-muted)";
}

function RankingRow({
  rankLabel,
  teamName,
  avatarUrl,
  ownerName,
  primaryMetric,
  metricLabel,
  toneColor,
  isCurrent,
  firstPlace,
  secondary,
  badges,
  onOpen,
}: {
  rankLabel: string;
  teamName: string;
  avatarUrl?: string | null;
  ownerName: string | null;
  primaryMetric: string;
  metricLabel: string;
  toneColor: string;
  isCurrent?: boolean;
  firstPlace?: boolean;
  secondary?: string[];
  badges?: { label: string; tone?: "positive" | "negative" | "neutral" }[];
  /** Opens the manager profile (Manager Tendencies) for this team. */
  onOpen?: () => void;
}) {
  return (
    <div
      role={onOpen ? "button" : undefined}
      tabIndex={onOpen ? 0 : undefined}
      aria-label={onOpen ? `${teamName} manager profile` : undefined}
      onClick={onOpen}
      onKeyDown={onOpen ? (event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); onOpen(); } } : undefined}
      className={`flex items-center gap-3 py-2.5 px-1${onOpen ? " cursor-pointer" : ""}`}
      style={{
        borderBottom: "var(--border-width-default) solid var(--color-border)",
        background: isCurrent ? "var(--color-accent-soft)" : "transparent",
      }}
    >
      <span
        className="text-sm font-extrabold shrink-0 text-center"
        style={{ color: firstPlace ? "var(--color-premium)" : "var(--color-text-muted)", minWidth: "2.25rem" }}
      >
        {rankLabel}
      </span>
      <TeamAvatar avatarUrl={avatarUrl} size={32} ringColor={firstPlace ? "var(--color-premium)" : "var(--color-border)"} />
      <div className="flex-1 flex flex-col gap-0.5 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-sm font-bold break-words" style={{ color: "var(--color-text-primary)" }}>
            {teamName}
          </span>
          {isCurrent ? <ToneBadge label="You" color={rankBadgeColor("positive")} /> : null}
        </div>
        <span className="text-xs break-words" style={{ color: "var(--color-text-muted)" }}>
          {ownerName || "Manager"}
        </span>
        {secondary && secondary.length > 0 ? (
          <span className="text-xs break-words" style={{ color: "var(--color-text-muted)" }}>
            {secondary.join(" · ")}
          </span>
        ) : null}
        {badges && badges.length > 0 ? (
          <div className="flex flex-wrap gap-1.5 mt-0.5">
            {badges.map((badge) => (
              <ToneBadge key={badge.label} label={badge.label} color={rankBadgeColor(badge.tone)} />
            ))}
          </div>
        ) : null}
      </div>
      <div className="flex flex-col items-end gap-0.5 shrink-0">
        <span className="text-sm font-extrabold" style={{ color: toneColor }}>
          {primaryMetric}
        </span>
        <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          {metricLabel}
        </span>
      </div>
    </div>
  );
}

type OpenManager = (rosterId: string, teamName: string, ownerName: string | null, avatarUrl: string | null) => void;

function StandingsSection({ data, myRosterId, onOpenManager }: { data: LeagueTeamRankingsResponse; myRosterId: string; onOpenManager: OpenManager }) {
  const title = data.season ? `${data.season} Standings` : "Standings";

  if (!data.standings_available) {
    return (
      <section className="flex flex-col gap-3">
        <SectionHeading
          kicker="Where you stand"
          note="Actual results from league matchups — separate from Roster Power strength."
        >
          {title}
        </SectionHeading>
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
          {data.standings_message || "Standings will populate once regular-season results are available."}
        </p>
      </section>
    );
  }

  const ordered = sortByStanding(data.teams);

  return (
    <section className="flex flex-col gap-3">
      <SectionHeading
        kicker="Where you stand"
        note={`${data.week_label ? `${data.week_label} — ` : ""}Actual results from league matchups — separate from Roster Power strength.`}
      >
        {title}
      </SectionHeading>
      <div className="glass-surface flex flex-col">
        {ordered.map((team) => {
          const percentile = percentileFromRank(team.standing_rank, ordered.length);
          const secondary = [`Win% ${team.win_pct_label ?? "—"}`, `PF ${team.points_for_label ?? "0.0"}`, `PA ${team.points_against_label ?? "0.0"}`];
          return (
            <div key={team.roster_id}>
              <RankingRow
                rankLabel={formatRank(team.standing_rank)}
                teamName={team.team_name || "Team"}
                avatarUrl={team.avatar_url}
                ownerName={team.owner_name}
                primaryMetric={team.record_label || "0-0"}
                metricLabel="Record"
                toneColor={metricToneColor(percentile)}
                isCurrent={team.roster_id === myRosterId}
                firstPlace={team.standing_rank === 1}
                secondary={secondary}
                badges={team.playoff_status ? [{ label: team.playoff_status, tone: "neutral" }] : undefined}
                onOpen={() => onOpenManager(team.roster_id, team.team_name || "Team", team.owner_name, team.avatar_url)}
              />
              {team.on_playoff_line ? (
                <div
                  className="text-xs font-bold uppercase text-center py-1"
                  style={{ color: "var(--color-accent)", letterSpacing: "var(--letter-spacing-badge)" }}
                  role="separator"
                  aria-label="Playoff line"
                >
                  Playoff line
                </div>
              ) : null}
            </div>
          );
        })}
      </div>
    </section>
  );
}

function PlayoffOddsRow({ team, rankLabel, myRosterId }: { team: PlayoffOddsTeam; rankLabel: string; myRosterId: string }) {
  const statusBadge = team.clinched
    ? { label: "Clinched", tone: "positive" as const }
    : team.eliminated
      ? { label: "Eliminated", tone: "negative" as const }
      : undefined;
  return (
    <RankingRow
      rankLabel={rankLabel}
      teamName={team.team_name || "Team"}
      avatarUrl={team.avatar_url}
      ownerName={team.owner_name}
      primaryMetric={`${Math.round(team.playoff_probability)}%`}
      metricLabel="Playoff Odds"
      toneColor={metricToneColor(team.playoff_probability)}
      isCurrent={team.roster_id === myRosterId}
      firstPlace={rankLabel === "#1"}
      secondary={[`Proj ${team.median_final_wins}-${team.median_final_losses}`, `Seed #${team.median_seed}`, team.record_label || "0-0"]}
      badges={statusBadge ? [statusBadge] : undefined}
    />
  );
}

function PlayoffOddsSection({ leagueId, myRosterId }: { leagueId: string; myRosterId: string }) {
  const [state, setState] = useState<"idle" | "loading" | "error" | "ready">("idle");
  const [result, setResult] = useState<PlayoffOddsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const calculate = () => {
    setState("loading");
    setError(null);
    api
      .getLeaguePlayoffOdds(leagueId)
      .then((response) => {
        setResult(response);
        setState("ready");
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : "Could not calculate playoff odds.");
        setState("error");
      });
  };

  return (
    <section className="flex flex-col gap-3">
      <SectionHeading
        kicker="What might happen next"
        note="A real Monte Carlo simulation of the rest of the season — your real schedule, real Roster Power, thousands of simulated outcomes."
      >
        Playoff Odds
      </SectionHeading>
      <BeginnerHelp term="playoffOddsIntro" />
      <BeginnerHelp term="playoffOddsTerms" />
      {state === "idle" ? (
        <button
          type="button"
          onClick={calculate}
          className="self-start px-4 py-2.5 text-sm font-bold"
          style={{ background: "var(--color-accent)", color: "var(--color-bg)" }}
        >
          Calculate playoff odds
        </button>
      ) : null}
      {state === "loading" ? (
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
          Running thousands of simulated outcomes…
        </p>
      ) : null}
      {state === "error" ? (
        <p className="text-sm" role="alert" style={{ color: "var(--color-danger)" }}>
          {error}
        </p>
      ) : null}
      {state === "ready" && result ? (
        result.reason || result.teams.length === 0 ? (
          <EmptyState title={playoffOddsReasonMessage(result.reason)} />
        ) : (
          <div className="glass-surface flex flex-col">
            {result.teams.map((team, index) => (
              <PlayoffOddsRow key={team.roster_id} team={team} rankLabel={formatRank(index + 1)} myRosterId={myRosterId} />
            ))}
          </div>
        )
      ) : null}
    </section>
  );
}

function RankBoardSection({ board, teams, myRosterId, onOpenManager }: { board: RankBoardKey; teams: TeamRanking[]; myRosterId: string; onOpenManager: OpenManager }) {
  const config = RANK_BOARD_CONFIG[board];
  const ordered = sortByBoard(teams, board);

  return (
    <section className="flex flex-col gap-3">
      <SectionHeading kicker={config.kicker} note={config.note}>{config.title}</SectionHeading>
      <div className="glass-surface flex flex-col">
        {ordered.map((team) => {
          const rank = team[config.rankField] as number | null;
          const tied = Boolean(team[config.tiedField]);
          const score = team[config.scoreField] as number | null;
          const percentile = percentileFromRank(rank, ordered.length);
          const badges: { label: string; tone?: "positive" | "negative" | "neutral" }[] = [];
          if (team.archetype_label) badges.push({ label: team.archetype_label, tone: "neutral" });
          if (team.health_flag && team.health_flag !== "Stable") {
            badges.push({ label: team.health_flag, tone: "negative" });
          }
          (team.team_badges || []).forEach((label) => badges.push({ label, tone: teamBadgeTone(label) }));
          return (
            <RankingRow
              key={team.roster_id}
              rankLabel={formatRank(rank, tied)}
              teamName={team.team_name || "Team"}
              avatarUrl={team.avatar_url}
              ownerName={team.owner_name}
              primaryMetric={formatScore(score)}
              metricLabel={config.scoreLabel}
              toneColor={metricToneColor(percentile)}
              isCurrent={team.roster_id === myRosterId}
              firstPlace={rank === 1}
              secondary={boardSecondaryParts(board, team)}
              badges={badges}
              onOpen={() => onOpenManager(team.roster_id, team.team_name || "Team", team.owner_name, team.avatar_url)}
            />
          );
        })}
      </div>
    </section>
  );
}

export function LeagueRankingsContent({
  leagueId,
  leagueName,
  data,
  myRosterId = "",
}: {
  leagueId: string;
  leagueName: string;
  data: LeagueTeamRankingsResponse;
  /** The signed-in user's own roster_id in this league, if resolvable —
   * powers the "You" highlight each board already shows elsewhere
   * (My Team's Team Snapshot, Matchup). Empty when it couldn't be resolved
   * (e.g. no linked Sleeper username); every row just renders unhighlighted
   * in that case, same as the other pages' best-effort "You" badge. */
  myRosterId?: string;
}) {
  const notReady = !data.ok || data.teams.length === 0;
  const [profile, setProfile] = useState<{ rosterId: string; teamName: string; ownerName: string | null; avatarUrl: string | null } | null>(null);
  const openManager: OpenManager = (rosterId, teamName, ownerName, avatarUrl) => setProfile({ rosterId, teamName, ownerName, avatarUrl });

  return (
    <main className="flex-1 flex flex-col gap-8 px-4 py-8 max-w-3xl w-full mx-auto">
      <header className="flex flex-col gap-1">
        <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          League Rankings
        </span>
        <h1 style={{ font: "var(--font-page-title)" }}>{leagueName}</h1>
      </header>

      {notReady ? (
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
          {teamRankingsReasonMessage(data.reason)}
        </p>
      ) : (
        <>
          <StandingsSection data={data} myRosterId={myRosterId} onOpenManager={openManager} />
          <PlayoffOddsSection leagueId={leagueId} myRosterId={myRosterId} />
          <RankBoardSection board="power" teams={data.teams} myRosterId={myRosterId} onOpenManager={openManager} />
          <RankBoardSection board="franchise" teams={data.teams} myRosterId={myRosterId} onOpenManager={openManager} />
          <RankBoardSection board="draft_capital" teams={data.teams} myRosterId={myRosterId} onOpenManager={openManager} />
          <RankBoardSection board="starter" teams={data.teams} myRosterId={myRosterId} onOpenManager={openManager} />
          <RankBoardSection board="bench" teams={data.teams} myRosterId={myRosterId} onOpenManager={openManager} />
        </>
      )}
      {profile ? (
        <ManagerProfileSheet
          leagueId={leagueId}
          rosterId={profile.rosterId}
          teamName={profile.teamName}
          ownerName={profile.ownerName}
          avatarUrl={profile.avatarUrl}
          onClose={() => setProfile(null)}
        />
      ) : null}
      <ValuesCredit />
    </main>
  );
}
