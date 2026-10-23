import { SectionHeading } from "@/components/SectionHeading";
import Link from "next/link";

import type { DashboardResponse, LeagueTeamRankingsResponse } from "@/lib/api";
import { BeginnerHelp } from "@/components/BeginnerHelp";
import { GamePlanCard } from "@/components/GamePlanCard";
import { GuillotineCard, LeagueTypeControl, useGuillotineState } from "@/components/GuillotineCard";
import { GuessThePlayerCard } from "@/components/GuessThePlayerCard";
import { GuessThePlayerNameMatchCard } from "@/components/GuessThePlayerNameMatchCard";
import { LeaguePulseCard } from "@/components/LeaguePulseCard";
import { EmptyState } from "@/components/EmptyState";
import { formatRank } from "@/components/SnapshotTile";
import { StatStrip } from "@/components/StatStrip";
import { ThisWeekStrip } from "@/components/ThisWeekStrip";
import { thisWeekTradeIdeaHeadline } from "@/lib/thisWeek";
import { WatchListCard } from "@/components/WatchListCard";
import { useExperienceCopy } from "@/context/ExperienceLevelContext";
import { notReadyReasonMessage } from "@/lib/notReadyMessages";

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
}: {
  leagueId: string;
  leagueName: string;
  data: DashboardResponse;
  /** League Pulse's source, already in flight (the page starts it alongside
   * the Dashboard request). Omitted: the tile fetches it itself. */
  teamRankings?: Promise<LeagueTeamRankingsResponse>;
}) {
  const snapshot = data.team_snapshot;
  const { data: guillotine, reload: reloadGuillotine } = useGuillotineState(leagueId);
  // Beginner helper text (onboarding experience level) — null/undefined for
  // advanced or unset accounts, so every tile below renders as before.
  const copy = useExperienceCopy();
  const query = `?name=${encodeURIComponent(leagueName)}`;
  // The trade idea the This week strip already shows is not repeated as a Today card.
  const duplicateTradeHeadline = thisWeekTradeIdeaHeadline(data.this_week);
  const allTopItems = data.items.filter((item) => item.category === "top_priority");
  const topItems = duplicateTradeHeadline
    ? allTopItems.filter((item) => (item.headline ?? "").trim() !== duplicateTradeHeadline)
    : allTopItems;
  const droppedDuplicate = topItems.length < allTopItems.length;
  const watchItems = data.items.filter((item) => item.category !== "top_priority");

  return (
    // coridian_, 2026-10-17 (screenshot): too much empty space above the
    // first real card on Dashboard — the one page most people land on
    // first. Tighter top padding/section gap than the other pages' shared
    // shell (gap-8 px-4 py-8) and the "Today's Game Plan" subtitle dropped
    // (it only restated what the heading already said; the real content —
    // the actionable cards below — is what should hit the fold).
    <main className="flex-1 flex flex-col gap-6 px-4 py-5 max-w-3xl w-full mx-auto">
      {/* The page title lives in the persistent Header (level with search and
          alerts); the league name stays here as the page's <h1> for screen
          readers and is already in the header's league switcher. */}
      <h1 className="sr-only">{leagueName}</h1>

      <GuillotineCard data={guillotine} />

      {snapshot ? (
        <section className="flex flex-col gap-2" aria-label="Team summary">
          <StatStrip
            columns={4}
            items={[
              { glyph: "record", label: "Record", value: `${snapshot.wins ?? 0}-${snapshot.losses ?? 0}${snapshot.ties ? `-${snapshot.ties}` : ""}` },
              {
                glyph: "power",
                label: "Power Rank",
                value: formatRank(snapshot.power_rank, snapshot.power_rank_tied),
                tone: snapshot.power_rank === 1 ? "premium" : "neutral",
              },
              {
                glyph: "franchise",
                label: "Franchise Rank",
                value: formatRank(snapshot.franchise_rank, snapshot.franchise_rank_tied),
                tone: snapshot.franchise_rank === 1 ? "premium" : "neutral",
              },
              {
                glyph: "age",
                label: copy.label("averageAge", "Avg Age"),
                value: snapshot.average_age !== null ? snapshot.average_age.toFixed(1) : "—",
              },
            ]}
          />
          {/* Beginner term explanations as short lines under the strip, like
              the mobile Dashboard. As per-tile captions inside four 390px-wide
              columns they were ~450px tall and pushed Today below the fold. */}
          <BeginnerHelp text={copy.help("powerRank") ? `Power Rank: ${copy.help("powerRank")}` : null} />
          <BeginnerHelp text={copy.help("franchiseRank") ? `Franchise Rank: ${copy.help("franchiseRank")}` : null} />
          <BeginnerHelp text={copy.help("averageAge") ? `Average Age: ${copy.help("averageAge")}` : null} />
        </section>
      ) : null}

      {data.this_week ? <ThisWeekStrip data={data.this_week} leagueId={leagueId} leagueName={leagueName} tradePending={Boolean(data.trade_ideas_deferred)} /> : null}

      {droppedDuplicate && topItems.length === 0 && watchItems.length === 0 && data.entitlement.hidden_count <= 0 ? null : (
      <section className="flex flex-col gap-3" aria-labelledby="game-plan-heading" data-fgl-dashboard-useful="true">
        <SectionHeading id="game-plan-heading" action={<ViewAllLink href={`/gm-plan/${encodeURIComponent(leagueId)}${query}`} label="View all game plan items" />}>
          Today
        </SectionHeading>
        <BeginnerHelp term="dashboardGamePlan" />

        {topItems.length === 0 && watchItems.length === 0 ? (
          <EmptyState
            title={
              notReadyReasonMessage(data.reason, {
                linkAccount: "Connect your Sleeper account to see your Game Plan.",
                emptyRoster: "Your roster doesn't have any players yet. This is expected if your draft is still in progress.",
              }) || "No urgent roster issues right now."
            }
          >
            {!data.reason ? <BeginnerHelp term="dashboardNothingUrgent" className="mt-1" /> : null}
          </EmptyState>
        ) : (
          topItems.map((item) => (
            <GamePlanCard key={item.recommendation_id || item.headline} item={item} leagueId={leagueId} leagueName={leagueName} />
          ))
        )}

        {data.entitlement.hidden_count > 0 ? (
          <div
            className="p-4 flex flex-col gap-2"
            style={{ background: "var(--color-action-soft)", border: "var(--border-width-default) solid var(--color-action)" }}
          >
            <p className="text-sm font-bold">
              {data.entitlement.hidden_count} more move{data.entitlement.hidden_count === 1 ? "" : "s"} available on Premium.
            </p>
            <Link href="/premium" className="text-sm font-bold self-start" style={{ color: "var(--color-premium)" }}>
              Upgrade →
            </Link>
          </div>
        ) : null}
      </section>
      )}

      {watchItems.length > 0 ? (
        <section className="flex flex-col gap-3" aria-labelledby="watchlist-heading">
          <SectionHeading id="watchlist-heading" action={<ViewAllLink href={`/alerts/${encodeURIComponent(leagueId)}${query}`} label="View all alerts" />}>
            Watchlist &amp; Alerts
          </SectionHeading>
          <WatchListCard items={watchItems} leagueId={leagueId} leagueName={leagueName} />
        </section>
      ) : null}

      {/* League Activity and Guess the Player side by side (stacked on a
          phone-narrow viewport, where the playable game needs the width).
          Both self-fetch and render nothing on failure; a lone card takes
          the full row. */}
      <div className="grid grid-cols-1 sm:grid-cols-2 items-start gap-3 [&>*:only-child]:sm:col-span-2">
        <LeaguePulseCard leagueId={leagueId} leagueName={leagueName} teamRankings={teamRankings} />
        <GuessThePlayerCard leagueId={leagueId} leagueName={leagueName} />
      </div>
      <GuessThePlayerNameMatchCard leagueId={leagueId} leagueName={leagueName} />

      {snapshot ? (
        <section className="flex flex-col gap-3" aria-labelledby="snapshot-heading" data-fgl-dashboard-complete="true">
          <SectionHeading id="snapshot-heading">Team Snapshot</SectionHeading>
          <BeginnerHelp term="dashboardSnapshot" />
          <StatStrip
            columns={3}
            items={[
              {
                glyph: "starter",
                label: "Starter Strength",
                value: formatRank(snapshot.starter_rank, snapshot.starter_rank_tied),
                tone: snapshot.starter_rank === 1 ? "premium" : "neutral",
              },
              {
                glyph: "bench",
                label: "Bench Strength",
                value: formatRank(snapshot.bench_rank, snapshot.bench_rank_tied),
                tone: snapshot.bench_rank === 1 ? "premium" : "neutral",
              },
              {
                glyph: "injury",
                label: "Injuries",
                value: snapshot.health_flag || "Stable",
                tone: snapshot.injured_starters && snapshot.injured_starters > 0 ? "risk" : "positive",
              },
            ]}
          />
          <BeginnerHelp text={copy.help("starterStrength") ? `Starter Strength: ${copy.help("starterStrength")}` : null} />
          <BeginnerHelp text={copy.help("benchStrength") ? `Bench Strength: ${copy.help("benchStrength")}` : null} />
        </section>
      ) : null}
      <LeagueTypeControl leagueId={leagueId} data={guillotine} onChanged={reloadGuillotine} />
    </main>
  );
}

function ViewAllLink({ href, label }: { href: string; label: string }) {
  return (
    <Link href={href} aria-label={label} className="text-sm font-bold shrink-0" style={{ color: "var(--color-accent)" }}>
      View All →
    </Link>
  );
}
