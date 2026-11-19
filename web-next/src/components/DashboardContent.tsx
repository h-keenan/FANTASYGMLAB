import { FreshnessLabel } from "@/components/ui/FreshnessLabel";
import dynamic from "next/dynamic";
import Link from "next/link";
import { TERMS } from "@/lib/terms";
import { ModuleMore } from "@/components/ui/ModuleMore";
import { useEffect, useState, type MouseEvent } from "react";

import { api, type DashboardResponse, type LeagueTeamRankingsResponse } from "@/lib/api";
import { NextSteps } from "@/components/NextSteps";
import { GuillotineCard, LeagueTypeControl, useGuillotineState } from "@/components/GuillotineCard";
import { formatRank, rankFill } from "@/components/SnapshotTile";
import type { StatStripItem } from "@/components/StatStrip";
import { StatStripModule } from "@/components/ui/ModuleTemplates";
import { useTeamStatusData, type TeamStatusPrefetch } from "@/lib/useTeamStatusData";
import { leagueAverageAge } from "@/lib/teamStatus";
import { useSeasonOdds } from "@/components/DashboardOddsStrip";
import { DashboardMore } from "@/components/DashboardBlocks";
import { SkeletonHero } from "@/components/Skeleton";
import { TodayMatchupCard } from "@/components/TodayMatchupCard";
import { TodayRooms, TodayTiles, TodayTradeIdeaCard } from "@/components/TodayGlance";
import { GAME_PLAN_INTERNAL_ROUTES, gamePlanTileHref, resolveGamePlanTargetPlayerId } from "@/lib/gamePlanPresentation";
import { DecisionQueue } from "@/components/DecisionQueue";
import { buildDecisionQueue } from "@/lib/decisionQueue";
import { notReadyReasonMessage } from "@/lib/notReadyMessages";
import { useExperienceCopy } from "@/context/ExperienceLevelContext";
import { deadlineChip, isTradeItem, TRADES_BLOCK_COPY, tradesStanceLine } from "@/lib/dashboardLayout";
import { buildTeamStatusMatchup, buildTeamStatusOdds, buildTeamStatusPositions, buildTeamStatusStanding } from "@/lib/teamStatus";
import { todayRoomChips, todayTiles, todayTradeIdea } from "@/lib/todayView";

// Below-the-fold and conditional modules load as their own chunks (after the above-the-fold content has hydrated), so they are not
// part of Today's first-load JS. Each renders nothing until its chunk lands; none sits above the matchup card.
const GuessThePlayerCard = dynamic(() => import("@/components/GuessThePlayerCard").then((m) => m.GuessThePlayerCard), { loading: () => null });
const GuessThePlayerNameMatchCard = dynamic(() => import("@/components/GuessThePlayerNameMatchCard").then((m) => m.GuessThePlayerNameMatchCard), { loading: () => null });
const LeaguePulseCard = dynamic(() => import("@/components/LeaguePulseCard").then((m) => m.LeaguePulseCard), { loading: () => null });
const StartHereCard = dynamic(() => import("@/components/StartHereCard").then((m) => m.StartHereCard), { loading: () => null });
const FirstValueOfferCard = dynamic(() => import("@/components/FirstValueOfferCard").then((m) => m.FirstValueOfferCard), { loading: () => null });
const DirectionCheckinCard = dynamic(() => import("@/components/DirectionCheckinCard").then((m) => m.DirectionCheckinCard), { loading: () => null });
const DashboardAlerts = dynamic(() => import("@/components/DashboardAlerts").then((m) => m.DashboardAlerts), { loading: () => null });

/**
 * Ports modules/dashboard_workflow.py's render_dashboard_workflow for
 * Revision 1 (see PR description for exactly what's deferred: What
 * Changed, roster-aware News Alert tiles, league recap teaser, orientation
 * tour, startup-mode/ESPN-degraded variants — all of those need either a
 * new engine endpoint beyond a thin wrapper or are Streamlit-session-state-
 * shaped and aren't core to this milestone). League Pulse, originally
 * deferred for the same reason, now has its own thin wrapper after all —
 * GET .../team-rankings' real transaction_activity_count/current_streak
 * fields (modules.manager_activity/modules.team_streaks) — see
 * LeaguePulseCard.tsx.
 * Covers: Today's Game Plan (GET .../dashboard's `items`, entitlement-
 * capped) and Team Snapshot (the same response's `team_snapshot`, which on
 * this backend already combines web's separate League Snapshot + Team
 * Snapshot tile rows into one object).
 *
 * Pulled out of app/dashboard/[leagueId]/page.tsx as a pure presentational
 * component (data in, markup out) so it can be smoke-tested directly with
 * a fixture, without needing to mock Supabase auth/fetch.
 */

export function DashboardContent({
  leagueId,
  leagueName,
  data,
  teamRankings,
  prefetch,
  userId,
  accountCreatedAt,
  sample,
  lens = "Dynasty",
}: {
  /** Valuation lens the page loaded the Dashboard with, reused for the hero's reads. */
  lens?: string;
  leagueId: string;
  leagueName: string;
  data: DashboardResponse;
  /** League Pulse's source, already in flight (the page starts it alongside
   * the Dashboard request). Omitted: the tile fetches it itself. */
  teamRankings?: Promise<LeagueTeamRankingsResponse>;
  /** The hero's matchup / roster-needs reads, also started by the page. */
  prefetch?: TeamStatusPrefetch;
  /** Signed-in user, for the first-run Start here card (omitted: no card). */
  userId?: string;
  accountCreatedAt?: string | null;
  /** Sample-league preview (static fictional `data`, see lib/sampleDashboard.ts):
   * renders the same modules without any fetch (no Guillotine lookup, no
   * games, no league-type control), inside a plain container instead of
   * <main>, and turns every link into a no-op that calls `onBlockedLink`. */
  sample?: { onBlockedLink: () => void };
}) {
  const snapshot = data.team_snapshot;
  const { data: guillotine, reload: reloadGuillotine } = useGuillotineState(sample ? undefined : leagueId);
  // Beginner helper text (onboarding experience level) — null/undefined for
  // advanced or unset accounts, so every tile below renders as before.
  const copy = useExperienceCopy();
  // The league's real GM stance (what trade advice is tuned by), shown on the trade line for beginners.
  const [stance, setStance] = useState<string>("");
  const showStance = copy.isBeginner && !sample;
  useEffect(() => {
    if (!showStance || !leagueId) return;
    let cancelled = false;
    api
      .getTeamStance(leagueId)
      .then((res) => {
        if (!cancelled) setStance(res.stance || "");
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [showStance, leagueId]);
  const query = `?name=${encodeURIComponent(leagueName)}`;
  const Shell: "div" | "main" = sample ? "div" : "main";
  const watchItems = data.items.filter((item) => item.category !== "top_priority");
  // Module order: lib/dashboardLayout.ts DASHBOARD_MODULE_ORDER. Trade ideas are
  // one line (count + Trade Hub link); urgent items sit once in "Needs
  // attention"; "This week" keeps only what is left, so nothing shows twice.
  const tradeItems = data.items.filter((item) => item.category === "top_priority" && isTradeItem(item));
  // Decision Queue state is computed below, once the matchup read has settled.
  // My Team: six equal tiles (the odds come from the season simulator; until
  // it has something real the two slots hold Starter / Bench Strength), the
  // rest behind "More team stats".
  // The season simulation is the heaviest read on this page and only feeds one
  // hero number, so it starts once the first pass has painted and the server
  // is no longer busy with the trade-idea search.
  const { sim } = useSeasonOdds(leagueId, !sample && !data.trade_ideas_deferred);
  const teamStatus = useTeamStatusData(leagueId, lens, !sample, teamRankings, prefetch);
  const teams = teamStatus.rankings?.teams ?? null;
  // The Decision Queue (lib/decisionQueue.ts): ONE ranked, deduped list of what needs a decision (lineup swaps, waivers,
  // deadline, injuries, draft events). Until the matchup read has settled the queue is a skeleton, so nothing moves when
  // the lineup problems land.
  const matchupLine = buildTeamStatusMatchup(teamStatus.matchup);
  const queue = buildDecisionQueue({
    now: new Date(),
    moves: teamStatus.matchup?.suggested_moves,
    openSlots: teamStatus.matchup?.open_slots?.length ?? 0,
    thisWeek: data.this_week,
    items: data.items,
    tradeWindow: data.trade_window,
    tradeIdeaCount: tradeItems.length,
    entitlement: data.entitlement ? { isPremium: data.entitlement.is_premium, hiddenCount: data.entitlement.hidden_count } : null,
    nextGame: matchupLine ? { week: matchupLine.week, opponentName: matchupLine.opponentName } : data.this_week?.week ? { week: data.this_week.week, opponentName: "" } : null,
    injuredStarters: snapshot?.injured_starters ?? null,
  });
  // Holds the place only while the queue would otherwise read "nothing needs you" before the matchup has said otherwise.
  const queuePending = !sample && !teamStatus.settled && queue.total === 0;
  // The glance modules read the standing / odds / rooms models once; each fact lives in exactly one module.
  const standing = buildTeamStatusStanding({
    snapshot,
    rankings: teamStatus.rankings?.teams,
    standingsAvailable: teamStatus.rankings?.standings_available,
    myRosterId: teamStatus.matchup?.my_team?.roster_id,
    odds: buildTeamStatusOdds(sim),
  });
  const deadlinePassed = Boolean(data.trade_window?.trade_deadline_passed);
  const stanceLine = copy.isBeginner ? tradesStanceLine(stance) : "";
  const tiles = todayTiles({ standing, tradeCount: tradeItems.length, tradesClosed: deadlinePassed });
  const roomChips = todayRoomChips(buildTeamStatusPositions(teamStatus.needs));
  const idea = tradeItems[0] ? todayTradeIdea(tradeItems[0]) : null;
  const id = encodeURIComponent(leagueId);
  const tradeHubHref = `/trade-hub/${id}${query}`;
  const ideaHref = tradeItems[0]
    ? gamePlanTileHref(GAME_PLAN_INTERNAL_ROUTES[tradeItems[0].destination] ?? "trade-hub", leagueId, leagueName, resolveGamePlanTargetPlayerId(tradeItems[0]))
    : tradeHubHref;
  const teamStats = snapshot
    ? buildTeamStats(snapshot, copy.label("averageAge", "Avg Age"), {
        teamCount: teams && teams.length > 1 ? teams.length : null,
        leagueAge: leagueAverageAge(teams),
      })
    : null;

  return (
    // coridian_, 2026-10-17 (screenshot): too much empty space above the
    // first real card on Dashboard — the one page most people land on
    // first. Tighter top padding/section gap than the other pages' shared
    // shell (gap-8 px-4 py-8) and the "Today's Game Plan" subtitle dropped
    // (it only restated what the heading already said; the real content —
    // the actionable cards below — is what should hit the fold).
    <Shell
      className={sample ? "flex flex-col gap-6" : "flex-1 flex flex-col gap-5 px-4 py-3 max-w-3xl w-full mx-auto"}
      {...(sample
        ? {
            "data-testid": "sample-dashboard",
            "data-inert-links": "",
            onClickCapture: (event: MouseEvent) => {
              if ((event.target as HTMLElement).closest("a")) {
                event.preventDefault();
                event.stopPropagation();
                sample.onBlockedLink();
              }
            },
          }
        : {})}
    >
      {/* The page title lives in the persistent Header (level with search and
          alerts); the league name stays here as the page's <h1> for screen
          readers and is already in the header's league switcher. */}
      {sample ? null : <h1 className="sr-only">{leagueName}</h1>}

      {/* Served from last-known provider data after a failed refresh: say how old it is (shared FreshnessLabel). */}
      {data.sleeper_data_as_of ? <FreshnessLabel datasets={[]} report={null} leagueAsOf={data.sleeper_data_as_of} className="block text-xs" /> : null}

      {userId ? <StartHereCard userId={userId} accountCreatedAt={accountCreatedAt} leagueId={leagueId} leagueName={leagueName} /> : null}

      {data.platform_notice ? (
        <p className="m-0 text-xs" style={{ color: "var(--color-text-muted)" }} data-testid="platform-notice">
          {data.platform_notice}
        </p>
      ) : null}

      {/* This week's matchup: the one place Today states the score and the win chance (ring card, taps open the swing players). */}
      {!teamStatus.settled ? (
        <div aria-busy="true" data-testid="team-status-hero-loading">
          <SkeletonHero minHeight={92} />
        </div>
      ) : matchupLine ? (
        <TodayMatchupCard line={matchupLine} matchup={teamStatus.matchup} href={`/matchup/${id}${query}`} />
      ) : null}

      {/* A few times a season: does the declared direction still fit? Server-decided,
          dismissible, once per moment (modules/direction_checkin.py). */}
      {sample ? null : <DirectionCheckinCard leagueId={leagueId} />}

      <DecisionQueue
        queue={queue}
        leagueId={leagueId}
        leagueName={leagueName}
        pending={queuePending}
        entitlement={data.entitlement}
        emptyOverride={data.reason ? notReadyReasonMessage(data.reason, { linkAccount: "Connect your Sleeper account to see what to do today.", emptyRoster: "Your roster doesn't have any players yet. This is expected if your draft is still in progress." }) || undefined : undefined}
      />

      {/* First-run trial offer, after the person has seen their own Today
          briefing (paywall-after-connect). Dismissible; nothing is gated. */}
      {userId && !sample ? <FirstValueOfferCard userId={userId} isPremium={data.entitlement?.is_premium === true} /> : null}

      {teamStatus.settled ? (
        <>
          <TodayTiles tiles={tiles} hrefs={{ standing: `/league-rankings/${id}${query}`, playoffs: `/league-rankings/${id}${query}`, trades: tradeHubHref }} />
          {idea && !deadlinePassed ? <TodayTradeIdeaCard idea={idea} href={ideaHref} deadline={deadlineChip(data.trade_window)?.value.replace(/\s*\(.*\)$/, "")} info={copy.isBeginner ? TRADES_BLOCK_COPY.beginnerExplainer : null} /> : null}
          {copy.isBeginner && stanceLine ? (
            // The league's real GM stance (what the trade advice is tuned by). The trade explainer is the "?" on the idea card.
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1" data-testid="today-trade-help">
              <Link href={`/gm-plan/${id}${query}`} className="text-xs" style={{ color: "var(--color-text-secondary)" }} data-testid="dashboard-stance-line">
                {stanceLine} <span className="font-bold" style={{ color: "var(--color-accent)" }}>{TRADES_BLOCK_COPY.changeStance}</span>
              </Link>
            </div>
          ) : null}
          <TodayRooms chips={roomChips} tradeHref={tradeHubHref} />
        </>
      ) : null}

      {snapshot && teamStats ? (
        // My Team: a StatStripModule. Collapsed it reads "This season #3 · Long term #5 · Starters #2 · Bench #7"; the tiles
        // (each an insight link) and the glossary open on tap. The marker below is the "dashboard rendered" signal.
        <section aria-label="Team summary" data-fgl-dashboard-complete="true">
          <StatStripModule
            id="today.team"
            title="My Team"
            items={teamStats.main}
            league={{ id: leagueId, name: leagueName }}
            infoLines={[copy.help("dashboardSnapshot")]}
            footer={
              <>
                <ModuleMore href={`/my-team/${encodeURIComponent(leagueId)}${query}`}>Open My Team</ModuleMore>
              </>
            }
          />
        </section>
      ) : null}

      <GuillotineCard data={guillotine} />

      {/* GM Plan lives in More (the bar does not show it), so Today carries it as a standing next step. */}
      {sample ? null : <NextSteps title="Plan ahead" steps={["gm-plan", "waivers", "trade-hub"]} leagueId={leagueId} leagueName={leagueName} />}

      {/* Alerts (with the watchlist folded in) is a section of Today: avatars + newest headline collapsed, unread count badge, tap to expand, `#alerts` opens it. */}
      {sample ? null : <DashboardAlerts leagueId={leagueId} leagueName={leagueName} watchItems={watchItems} />}

      {/* The sample preview has no More section, so it keeps League Activity inline. */}
      {sample ? <LeaguePulseCard leagueId={leagueId} leagueName={leagueName} teamRankings={teamRankings} /> : null}

      {/* Secondary modules (the two mini-games are play, not decisions) stay
          collapsed behind "More" so they never push the actionable modules down. */}
      {sample ? null : (
        <DashboardMore>
          <LeaguePulseCard leagueId={leagueId} leagueName={leagueName} teamRankings={teamRankings} />
          <GuessThePlayerCard leagueId={leagueId} leagueName={leagueName} />
          <GuessThePlayerNameMatchCard leagueId={leagueId} leagueName={leagueName} />
          <LeagueTypeControl leagueId={leagueId} data={guillotine} onChanged={reloadGuillotine} />
        </DashboardMore>
      )}
    </Shell>
  );
}

/**
 * My Team tiles: the league ranks and roster-health facts the hero does not
 * carry (record, standing and odds live there). Each tile adds its context
 * only when the data exists: team count from team-rankings, league-average age
 * from the same response.
 */
function buildTeamStats(
  snapshot: NonNullable<DashboardResponse["team_snapshot"]>,
  ageLabel: string,
  context: { teamCount: number | null; leagueAge: string | null },
): { main: StatStripItem[] } {
  const ofTeams = context.teamCount ? `of ${context.teamCount} teams` : undefined;
  const WHY_BY_GLYPH = { power: "power_rank", franchise: "franchise_rank", starter: "starter_strength", bench: "bench_strength" } as const;
  const rank = (glyph: "power" | "franchise" | "starter" | "bench", label: string, value: number | null, tied: boolean, note?: string): StatStripItem => ({
    glyph,
    insight: glyph,
    why: WHY_BY_GLYPH[glyph],
    label,
    value: formatRank(value, tied),
    tone: value === 1 ? "premium" : "neutral",
    note: value != null ? note : undefined,
    fill: rankFill(value, context.teamCount),
  });
  const main: StatStripItem[] = [
    rank("power", TERMS.thisSeason, snapshot.power_rank, snapshot.power_rank_tied, ofTeams),
    rank("franchise", TERMS.longTerm, snapshot.franchise_rank, snapshot.franchise_rank_tied, ofTeams),
    rank("starter", "Starter Strength", snapshot.starter_rank, snapshot.starter_rank_tied, ofTeams),
    rank("bench", "Bench Strength", snapshot.bench_rank, snapshot.bench_rank_tied, ofTeams),
    {
      glyph: "age",
      insight: "age",
      label: ageLabel,
      value: snapshot.average_age !== null ? snapshot.average_age.toFixed(1) : "—",
      note: snapshot.average_age !== null && context.leagueAge ? `League avg ${context.leagueAge}` : undefined,
    },
  ];
  return { main };
}
