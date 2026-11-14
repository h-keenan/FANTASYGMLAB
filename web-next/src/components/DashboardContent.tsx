import Link from "next/link";
import type { MouseEvent } from "react";

import type { DashboardResponse, LeagueTeamRankingsResponse } from "@/lib/api";
import { BeginnerHelp } from "@/components/BeginnerHelp";
import { SinceLastVisitStrip } from "@/components/SinceLastVisitStrip";
import { DirectionCheckinCard } from "@/components/DirectionCheckinCard";
import { FirstValueOfferCard } from "@/components/FirstValueOfferCard";
import { StartHereCard } from "@/components/StartHereCard";
import { GuillotineCard, LeagueTypeControl, useGuillotineState } from "@/components/GuillotineCard";
import { GlossaryNote } from "@/components/GlossaryNote";
import { GuessThePlayerCard } from "@/components/GuessThePlayerCard";
import { GuessThePlayerNameMatchCard } from "@/components/GuessThePlayerNameMatchCard";
import { LeaguePulseCard } from "@/components/LeaguePulseCard";
import { formatRank } from "@/components/SnapshotTile";
import type { StatStripItem } from "@/components/StatStrip";
import { CompactModule } from "@/components/ui/CompactModule";
import { StatStripModule } from "@/components/ui/ModuleTemplates";
import { listSummaryParts } from "@/lib/moduleTemplates";
import { TeamStatusHero, useTeamStatusData, type TeamStatusPrefetch } from "@/components/TeamStatusHero";
import { leagueAverageAge } from "@/lib/teamStatus";
import { TodayModule } from "@/components/TodayModule";
import { WatchListCard } from "@/components/WatchListCard";
import { useSeasonOdds } from "@/components/DashboardOddsStrip";
import { DashboardMore, DashboardNeedsAttention, DashboardTradesBlock } from "@/components/DashboardBlocks";
import { useExperienceCopy, useExperienceLevel } from "@/context/ExperienceLevelContext";
import { buildNeedsAttention, isTradeItem, itemsAfterAttention, weekRowsAfterAttention } from "@/lib/dashboardLayout";

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
  const { goal } = useExperienceLevel();
  const query = `?name=${encodeURIComponent(leagueName)}`;
  const Shell: "div" | "main" = sample ? "div" : "main";
  const watchItems = data.items.filter((item) => item.category !== "top_priority");
  // Module order: lib/dashboardLayout.ts DASHBOARD_MODULE_ORDER. Trade ideas are
  // one line (count + Trade Hub link); urgent items sit once in "Needs
  // attention"; "This week" keeps only what is left, so nothing shows twice.
  const tradeItems = data.items.filter((item) => item.category === "top_priority" && isTradeItem(item));
  const attention = buildNeedsAttention(
    data.this_week?.rows,
    data.trade_window,
    data.items.filter((item) => item.category === "top_priority"),
  );
  const nextMovesData: DashboardResponse = {
    ...data,
    items: itemsAfterAttention(
      data.items.filter((item) => !tradeItems.includes(item)),
      attention,
    ),
    this_week: data.this_week ? { ...data.this_week, rows: weekRowsAfterAttention(data.this_week.rows, attention) } : data.this_week,
  };
  const deadlineInAttention = attention.some((entry) => entry.source === "deadline");
  // My Team: six equal tiles (the odds come from the season simulator; until
  // it has something real the two slots hold Starter / Bench Strength), the
  // rest behind "More team stats".
  // The season simulation is the heaviest read on this page and only feeds one
  // hero number, so it starts once the first pass has painted and the server
  // is no longer busy with the trade-idea search.
  const { caption: oddsCaption, sim } = useSeasonOdds(leagueId, !sample && !data.trade_ideas_deferred);
  const teamStatus = useTeamStatusData(leagueId, lens, !sample, teamRankings, prefetch);
  const teams = teamStatus.rankings?.teams ?? null;
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

      {userId ? <StartHereCard userId={userId} accountCreatedAt={accountCreatedAt} leagueId={leagueId} leagueName={leagueName} /> : null}

      {userId && !sample ? <SinceLastVisitStrip userId={userId} leagueId={leagueId} leagueName={leagueName} /> : null}

      {data.platform_notice ? (
        <p className="m-0 text-xs" style={{ color: "var(--color-text-muted)" }} data-testid="platform-notice">
          {data.platform_notice}
        </p>
      ) : null}

      <TeamStatusHero leagueId={leagueId} leagueName={leagueName} snapshot={snapshot} sim={sim} oddsCaption={oddsCaption} data={teamStatus} />

      {/* A few times a season: does the declared direction still fit? Server-decided,
          dismissible, once per moment (modules/direction_checkin.py). */}
      {sample ? null : <DirectionCheckinCard leagueId={leagueId} />}

      <DashboardNeedsAttention entries={attention} leagueId={leagueId} leagueName={leagueName} />

      <TodayModule data={nextMovesData} leagueId={leagueId} leagueName={leagueName} hideEmpty={attention.length > 0} />

      {/* First-run trial offer, after the person has seen their own Today
          briefing (paywall-after-connect). Dismissible; nothing is gated. */}
      {userId && !sample ? <FirstValueOfferCard userId={userId} isPremium={data.entitlement?.is_premium === true} /> : null}

      <DashboardTradesBlock
        data={data}
        tradeItems={tradeItems}
        leagueId={leagueId}
        leagueName={leagueName}
        isBeginner={copy.isBeginner}
        goal={goal}
        deadlineInAttention={deadlineInAttention}
      />

      {snapshot && teamStats ? (
        // My Team: a StatStripModule. Collapsed it reads "Power #3 · Franchise #5 · Starters #2 · Bench #7"; the tiles
        // (each an insight link) and the glossary open on tap. The marker below is the "dashboard rendered" signal.
        <section aria-label="Team summary" data-fgl-dashboard-complete="true">
          <StatStripModule
            id="today.team"
            title="My Team"
            items={teamStats.main}
            league={{ id: leagueId, name: leagueName }}
            action={<ViewAllLink href={`/my-team/${encodeURIComponent(leagueId)}${query}`} label="Open My Team" label2="Open →" />}
            footer={
              <>
                <BeginnerHelp
                  popover
                  label="My Team stats"
                  lines={[
                    copy.help("dashboardSnapshot"),
                    copy.help("powerRank") ? `Power Rank: ${copy.help("powerRank")}` : null,
                    copy.help("franchiseRank") ? `Franchise Rank: ${copy.help("franchiseRank")}` : null,
                    copy.help("averageAge") ? `Average Age: ${copy.help("averageAge")}` : null,
                    copy.help("starterStrength") ? `Starter Strength: ${copy.help("starterStrength")}` : null,
                    copy.help("benchStrength") ? `Bench Strength: ${copy.help("benchStrength")}` : null,
                  ]}
                />
                <GlossaryNote terms={["powerRank", "franchiseRank", "averageAge", "starterStrength", "benchStrength"]} />
              </>
            }
          />
        </section>
      ) : null}

      <GuillotineCard data={guillotine} />

      {watchItems.length > 0 ? (
        <CompactModule
          id="today.watchlist"
          title="Watchlist & Alerts"
          label="Watchlist and alerts"
          testId="dashboard-watchlist"
          tone="warning"
          parts={listSummaryParts({ count: watchItems.length, noun: "alert", highlights: [watchItems[0]?.headline] })}
          action={<ViewAllLink href={`/alerts/${encodeURIComponent(leagueId)}${query}`} label="View all alerts" label2="All →" />}
        >
          <WatchListCard items={watchItems} leagueId={leagueId} leagueName={leagueName} />
        </CompactModule>
      ) : null}

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
  const injured = snapshot.injured_starters && snapshot.injured_starters > 0 ? snapshot.injured_starters : 0;
  const ofTeams = context.teamCount ? `of ${context.teamCount} teams` : undefined;
  const rank = (glyph: "power" | "franchise" | "starter" | "bench", label: string, value: number | null, tied: boolean, note?: string): StatStripItem => ({
    glyph,
    insight: glyph,
    label,
    value: formatRank(value, tied),
    tone: value === 1 ? "premium" : "neutral",
    note: value != null ? note : undefined,
  });
  const main: StatStripItem[] = [
    rank("power", "Power Rank", snapshot.power_rank, snapshot.power_rank_tied, ofTeams),
    rank("franchise", "Franchise Rank", snapshot.franchise_rank, snapshot.franchise_rank_tied, ofTeams),
    rank("starter", "Starter Strength", snapshot.starter_rank, snapshot.starter_rank_tied, ofTeams),
    rank("bench", "Bench Strength", snapshot.bench_rank, snapshot.bench_rank_tied, ofTeams),
    {
      glyph: "age",
      insight: "age",
      label: ageLabel,
      value: snapshot.average_age !== null ? snapshot.average_age.toFixed(1) : "—",
      note: snapshot.average_age !== null && context.leagueAge ? `League avg ${context.leagueAge}` : undefined,
    },
    {
      glyph: "injury",
      insight: "injury",
      label: "Injured starters",
      value: injured > 0 ? String(injured) : "None",
      tone: injured > 0 ? "risk" : "positive",
    },
  ];
  return { main };
}

function ViewAllLink({ href, label, label2 = "View all →" }: { href: string; label: string; label2?: string }) {
  return (
    <Link href={href} aria-label={label} className="tap-link text-sm font-bold shrink-0" style={{ color: "var(--color-accent)" }}>
      {label2}
    </Link>
  );
}
