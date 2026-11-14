"use client";

import { PageTabBar } from "@/components/PageTabBar";
import { BEGINNER_HELP } from "@/lib/experienceCopy";
import { useEffect, useState } from "react";

import { AccentCard } from "@/components/AccentCard";
import { BeginnerHelp } from "@/components/BeginnerHelp";
import { Button } from "@/components/Button";
import { ValueRing } from "@/components/ValueRing";
import { api, type LeagueTeamRankingsResponse, type PlayoffOddsResponse, type PlayoffOddsTeam, type TeamRanking } from "@/lib/api";
import {
  boardSecondaryParts,
  formatRank,
  metricToneColor,
  percentileFromRank,
  playoffOddsReasonMessage,
  RANK_BOARD_CONFIG,
  sortByBoard,
  sortByStanding,
  teamBadgeTone,
  teamRankingsReasonMessage,
  type RankBoardKey,
  boardScoreText,
} from "@/lib/leagueRankingsPresentation";
import { ManagerProfileSheet } from "@/components/ManagerProfileSheet";
import { SectionHeading } from "@/components/SectionHeading";
import { CompactModule } from "@/components/ui/CompactModule";
import { TeamAvatar } from "@/components/TeamAvatar";
import { PremiumUpsellCard } from "@/components/PremiumUpsellCard";
import { ToneBadge } from "@/components/ToneBadge";
import { NextSteps } from "@/components/NextSteps";
import { ValuesCredit } from "@/components/ValuesCredit";
import { EmptyState } from "@/components/EmptyState";
import { rankBoardAnchor } from "@/lib/insightLinks";
import { PageTitle } from "@/components/PageTitle";

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

/** Rank boards stay scannable: a row shows its first few badges, the rest as "+N". */
const MAX_ROW_BADGES = 2;
/** Rank boards open on the leaders; "Show all" reveals the rest of the league. */
const BOARD_PREVIEW_COUNT = 3;

export function RankingRow({
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
          <span className="text-sm font-bold [overflow-wrap:anywhere]" style={{ color: "var(--color-text-primary)" }}>
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
            {badges.slice(0, MAX_ROW_BADGES).map((badge) => (
              <ToneBadge key={badge.label} label={badge.label} color={rankBadgeColor(badge.tone)} />
            ))}
            {badges.length > MAX_ROW_BADGES ? (
              <span className="text-xs self-center" style={{ color: "var(--color-text-muted)" }}>
                +{badges.length - MAX_ROW_BADGES}
              </span>
            ) : null}
          </div>
        ) : null}
      </div>
      <div className="flex flex-col items-end gap-0.5 shrink-0 max-w-[30%] text-right">
        <span className="text-sm font-extrabold" style={{ color: toneColor }}>
          {primaryMetric}
        </span>
        <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          {metricLabel}
        </span>
      </div>
      {onOpen ? <span className="sr-only">. Open manager profile</span> : null}
    </div>
  );
}

function ringTone(percent: number): "low" | "mid" | "high" {
  return percent < 34 ? "low" : percent < 67 ? "mid" : "high";
}

/** "You" hero above the boards: Roster Power percentile ring, record, and the other four ranks as mini bars. */
function YourStandingCard({ teams, myRosterId }: { teams: TeamRanking[]; myRosterId: string }) {
  const me = myRosterId ? teams.find((team) => team.roster_id === myRosterId) : undefined;
  if (!me) return null;
  const total = teams.length;
  const powerPercent = percentileFromRank(me.power_rank, total);
  const ring = powerPercent === null ? null : Math.round(powerPercent);
  const minis: { key: RankBoardKey; label: string }[] = [
    { key: "franchise", label: "Franchise" },
    { key: "draft_capital", label: "Draft Capital" },
    { key: "starter", label: "Starters" },
    { key: "bench", label: "Bench" },
  ];
  return (
    <section id="your-standing" className="scroll-mt-4" aria-label="Your standing" data-testid="your-standing">
    <AccentCard accent="var(--color-accent)" as="div">
      <div className="flex items-center gap-3">
        <ValueRing
          percent={ring}
          tone={ring === null ? "mid" : ringTone(ring)}
          display={ring === null ? "—" : `${ring}`}
          ariaLabel={ring === null ? "Roster Power percentile unavailable" : `Roster Power percentile ${ring}`}
          size="md"
        />
        <div className="flex flex-col min-w-0 flex-1">
          <span className="text-xs font-extrabold uppercase" style={{ color: "var(--color-accent)", letterSpacing: "var(--letter-spacing-badge)" }}>
            Your standing
          </span>
          <span className="text-base font-extrabold" style={{ color: "var(--color-text-primary)" }}>
            Roster Power {formatRank(me.power_rank, me.power_rank_tied)} of {total}
          </span>
          <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
            {me.record_label ? `Record ${me.record_label}` : "Record not available"}
            {me.standing_rank != null ? ` · Standings ${formatRank(me.standing_rank)}` : ""}
          </span>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-x-4 gap-y-2">
        {minis.map(({ key, label }) => {
          const config = RANK_BOARD_CONFIG[key];
          const rank = me[config.rankField] as number | null;
          const tied = Boolean(me[config.tiedField]);
          const percentile = percentileFromRank(rank, total);
          return (
            <div key={key} className="flex flex-col gap-1 min-w-0">
              <div className="flex items-baseline justify-between gap-2 text-xs">
                <span style={{ color: "var(--color-text-muted)" }}>{label}</span>
                <span className="font-extrabold" style={{ color: metricToneColor(percentile) }}>
                  {formatRank(rank, tied)}
                </span>
              </div>
              <div
                role="progressbar"
                aria-label={`${label} percentile`}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-valuenow={percentile === null ? 0 : Math.round(percentile)}
                className="h-1.5 w-full"
                style={{ background: "var(--color-surface-muted)" }}
              >
                <div className="h-full" style={{ width: `${percentile === null ? 0 : Math.round(percentile)}%`, background: metricToneColor(percentile) }} />
              </div>
            </div>
          );
        })}
      </div>
    </AccentCard>
    </section>
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
        <EmptyState title={data.standings_message || "Standings will populate once regular-season results are available."} />
      </section>
    );
  }

  const ordered = sortByStanding(data.teams);
  const first = ordered[0];
  const me = ordered.find((team) => team.roster_id === myRosterId);
  const recordOf = (team: TeamRanking) => `${team.wins ?? 0}-${team.losses ?? 0}${team.ties ? `-${team.ties}` : ""}`;
  const standingParts = [
    first ? { key: "first", text: `1. ${first.team_name || "Team"} ${recordOf(first)}`, strong: true } : null,
    me && me.standing_rank != null ? { key: "you", text: `You ${formatRank(me.standing_rank, false)} · ${recordOf(me)}`, tone: "accent" as const } : null,
    { key: "n", text: `${ordered.length} teams` },
  ];

  return (
    <section>
      <CompactModule id="league.standings" title={title} parts={standingParts}>
      <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
        {`${data.week_label ? `${data.week_label} — ` : ""}Actual results from league matchups — separate from Roster Power strength.`}
      </p>
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
      </CompactModule>
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

/** The one real fact the Playoff Odds wall can show a Free user: where they
 * stand right now, straight from this page's own standings. */
function playoffOddsExample(team: TeamRanking | undefined, leagueName: string): string | undefined {
  if (!team || team.standing_rank == null || !team.record_label) return undefined;
  const status = team.playoff_status ? ` (${team.playoff_status})` : "";
  return `Right now you're ${formatRank(team.standing_rank)} in ${leagueName} at ${team.record_label}${status}. Playoff Odds turns that into a real playoff chance.`;
}

function PlayoffOddsSection({ leagueId, leagueName, myRosterId, myTeam }: { leagueId: string; leagueName: string; myRosterId: string; myTeam?: TeamRanking }) {
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
    <section id="playoff-odds" className="flex flex-col gap-3 scroll-mt-4">
      <SectionHeading
        kicker="What might happen next"
        note="A real Monte Carlo simulation of the rest of the season — your real schedule, real Roster Power, thousands of simulated outcomes."
      >
        Playoff Odds
      </SectionHeading>
      <div className="flex flex-wrap gap-2">
        <BeginnerHelp label="playoff odds" lines={[BEGINNER_HELP.playoffOddsIntro, BEGINNER_HELP.playoffOddsTerms]} />
      </div>
      {state === "idle" ? (
        <Button onClick={calculate} className="self-start">
          Calculate playoff odds
        </Button>
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
      {state === "ready" && result && result.is_premium === false ? (
        <PremiumUpsellCard
          bare
          kicker="Playoff Odds"
          leagueName={leagueName}
          example={playoffOddsExample(myTeam, leagueName)}
          upsell={result.upsell ?? null}
          fallbackTitle="Your real shot at the playoffs"
          fallbackBody="Playoff Odds is a Pro feature: a rest-of-season simulation of your league's real schedule, every team's playoff chance and projected seed. Start your free trial to unlock it."
        />
      ) : null}
      {state === "ready" && result && result.is_premium !== false ? (
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
  const [expanded, setExpanded] = useState(false);
  const canCollapse = ordered.length > BOARD_PREVIEW_COUNT + 1;
  // Collapsed: the top three, plus the caller's own row if they sit below it.
  const visible = !canCollapse || expanded
    ? ordered
    : ordered.filter((team, index) => index < BOARD_PREVIEW_COUNT || team.roster_id === myRosterId);

  // A rank board is a compact module: collapsed it names the leader and where you sit; the Roster Power board (and any
  // board an insight link targets with #board-x) opens by default.
  const anchor = rankBoardAnchor(board);
  const [hashOpen, setHashOpen] = useState(false);
  useEffect(() => {
    if (typeof window !== "undefined" && window.location.hash === `#${anchor}`) setHashOpen(true);
  }, [anchor]);
  const leader = ordered[0];
  const mine = ordered.find((team) => team.roster_id === myRosterId);
  const mineRank = mine ? (mine[config.rankField] as number | null) : null;
  const parts = [
    leader ? { key: "leader", text: `1. ${leader.team_name || "Team"}`, strong: true } : null,
    mine && mineRank != null ? { key: "you", text: `You ${formatRank(mineRank, Boolean(mine[config.tiedField]))}`, tone: "accent" as const } : null,
    { key: "count", text: `${ordered.length} teams` },
  ];
  return (
    <section id={anchor} className="scroll-mt-4" data-testid={`rank-board-${board}`}>
      <CompactModule key={hashOpen ? "hash" : "idle"} id={`league.board.${board}`} title={config.title} parts={parts} defaultOpen={hashOpen || board === "power"} persist={!hashOpen}>
      <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>{config.note}</p>
      <div className="glass-surface flex flex-col">
        {visible.map((team) => {
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
              primaryMetric={boardScoreText(board, score)}
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
        {canCollapse ? (
          <button
            type="button"
            onClick={() => setExpanded((value) => !value)}
            aria-expanded={expanded}
            className="tap-link text-sm font-bold py-3"
            style={{ color: "var(--color-accent)" }}
          >
            {expanded ? "Show top 3" : `Show all ${ordered.length} teams`}
          </button>
        ) : null}
      </div>
      </CompactModule>
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
    <main className="page-shell">
      {leagueId ? <PageTabBar family="league" active="rankings" leagueId={leagueId} leagueName={leagueName} /> : null}
      <header className="flex flex-col gap-1">
        <PageTitle page="League Rankings" leagueName={leagueName} />
      </header>

      {notReady ? (
        <EmptyState title="Rankings aren't ready yet" subtitle={teamRankingsReasonMessage(data.reason)} />
      ) : (
        <>
          <YourStandingCard teams={data.teams} myRosterId={myRosterId} />
          <StandingsSection data={data} myRosterId={myRosterId} onOpenManager={openManager} />
          <PlayoffOddsSection leagueId={leagueId} leagueName={leagueName} myRosterId={myRosterId} myTeam={data.teams.find((team) => team.roster_id === myRosterId)} />
          <RankBoardSection board="power" teams={data.teams} myRosterId={myRosterId} onOpenManager={openManager} />
          <RankBoardSection board="franchise" teams={data.teams} myRosterId={myRosterId} onOpenManager={openManager} />
          <RankBoardSection board="draft_capital" teams={data.teams} myRosterId={myRosterId} onOpenManager={openManager} />
          <RankBoardSection board="starter" teams={data.teams} myRosterId={myRosterId} onOpenManager={openManager} />
          <RankBoardSection board="bench" teams={data.teams} myRosterId={myRosterId} onOpenManager={openManager} />
          <RankBoardSection board="age" teams={data.teams} myRosterId={myRosterId} onOpenManager={openManager} />
        </>
      )}
      {profile ? (
        <ManagerProfileSheet
          leagueId={leagueId}
          leagueName={leagueName}
          rosterId={profile.rosterId}
          teamName={profile.teamName}
          ownerName={profile.ownerName}
          avatarUrl={profile.avatarUrl}
          onClose={() => setProfile(null)}
        />
      ) : null}
      {notReady ? null : <NextSteps title="Make a move" steps={["trade-hub", "matchup"]} leagueId={leagueId} leagueName={leagueName} />}
      <ValuesCredit />
    </main>
  );
}
