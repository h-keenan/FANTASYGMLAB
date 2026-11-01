import { SectionHeading } from "@/components/SectionHeading";
import Link from "next/link";
import type { MouseEvent } from "react";

import type { DashboardResponse, LeagueTeamRankingsResponse } from "@/lib/api";
import { BeginnerHelp } from "@/components/BeginnerHelp";
import { StartHereCard } from "@/components/StartHereCard";
import { GuillotineCard, LeagueTypeControl, useGuillotineState } from "@/components/GuillotineCard";
import { GlossaryNote } from "@/components/GlossaryNote";
import { GuessThePlayerCard } from "@/components/GuessThePlayerCard";
import { GuessThePlayerNameMatchCard } from "@/components/GuessThePlayerNameMatchCard";
import { LeaguePulseCard } from "@/components/LeaguePulseCard";
import { formatRank } from "@/components/SnapshotTile";
import { StatStrip } from "@/components/StatStrip";
import { TodayModule } from "@/components/TodayModule";
import { WatchListCard } from "@/components/WatchListCard";
import { DashboardMore, DashboardNowStrip, DashboardTradesBlock } from "@/components/DashboardBlocks";
import { useExperienceCopy, useExperienceLevel } from "@/context/ExperienceLevelContext";
import { isTradeItem, nextMoveRowFilter } from "@/lib/dashboardLayout";

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
  userId,
  accountCreatedAt,
  sample,
}: {
  leagueId: string;
  leagueName: string;
  data: DashboardResponse;
  /** League Pulse's source, already in flight (the page starts it alongside
   * the Dashboard request). Omitted: the tile fetches it itself. */
  teamRankings?: Promise<LeagueTeamRankingsResponse>;
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
  // Module order: lib/dashboardLayout.ts DASHBOARD_MODULE_ORDER. The trade
  // idea and the trade row live in the Trades block, a "lineup set" row in the
  // Now strip; "Next moves" keeps only what is left, so nothing shows twice.
  const tradeItems = data.items.filter((item) => item.category === "top_priority" && isTradeItem(item));
  const nextMovesData: DashboardResponse = {
    ...data,
    items: data.items.filter((item) => !tradeItems.includes(item)),
    this_week: data.this_week ? { ...data.this_week, rows: data.this_week.rows.filter(nextMoveRowFilter) } : data.this_week,
  };

  return (
    // coridian_, 2026-10-17 (screenshot): too much empty space above the
    // first real card on Dashboard — the one page most people land on
    // first. Tighter top padding/section gap than the other pages' shared
    // shell (gap-8 px-4 py-8) and the "Today's Game Plan" subtitle dropped
    // (it only restated what the heading already said; the real content —
    // the actionable cards below — is what should hit the fold).
    <Shell
      className={sample ? "flex flex-col gap-6" : "flex-1 flex flex-col gap-6 px-4 py-5 max-w-3xl w-full mx-auto"}
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

      {data.platform_notice ? (
        <p className="m-0 text-xs" style={{ color: "var(--color-text-muted)" }} data-testid="platform-notice">
          {data.platform_notice}
        </p>
      ) : null}

      <DashboardNowStrip data={data} leagueId={leagueId} leagueName={leagueName} />

      <DashboardTradesBlock
        data={data}
        tradeItems={tradeItems}
        leagueId={leagueId}
        leagueName={leagueName}
        isBeginner={copy.isBeginner}
        goal={goal}
      />

      <TodayModule data={nextMovesData} leagueId={leagueId} leagueName={leagueName} />

      {snapshot ? (
        <section className="flex flex-col gap-3" aria-labelledby="snapshot-heading" data-fgl-dashboard-complete="true" aria-label="Team summary">
          <SectionHeading id="snapshot-heading" action={<ViewAllLink href={`/my-team/${encodeURIComponent(leagueId)}${query}`} label="Open My Team" label2="Open →" />}>
            My Team
          </SectionHeading>
          <BeginnerHelp term="dashboardSnapshot" />
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
          {/* Beginner term explanations as short lines under the strips (as
              per-tile captions inside narrow columns they pushed Today below the fold). */}
          <BeginnerHelp text={copy.help("powerRank") ? `Power Rank: ${copy.help("powerRank")}` : null} />
          <BeginnerHelp text={copy.help("franchiseRank") ? `Franchise Rank: ${copy.help("franchiseRank")}` : null} />
          <BeginnerHelp text={copy.help("averageAge") ? `Average Age: ${copy.help("averageAge")}` : null} />
          <BeginnerHelp text={copy.help("starterStrength") ? `Starter Strength: ${copy.help("starterStrength")}` : null} />
          <BeginnerHelp text={copy.help("benchStrength") ? `Bench Strength: ${copy.help("benchStrength")}` : null} />
          <GlossaryNote terms={["powerRank", "franchiseRank", "averageAge", "starterStrength", "benchStrength"]} />
        </section>
      ) : null}

      <GuillotineCard data={guillotine} />

      {watchItems.length > 0 ? (
        <section className="flex flex-col gap-3" aria-labelledby="watchlist-heading">
          <SectionHeading id="watchlist-heading" action={<ViewAllLink href={`/alerts/${encodeURIComponent(leagueId)}${query}`} label="View all alerts" />}>
            Watchlist &amp; Alerts
          </SectionHeading>
          <WatchListCard items={watchItems} leagueId={leagueId} leagueName={leagueName} />
        </section>
      ) : null}

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

function ViewAllLink({ href, label, label2 = "View All →" }: { href: string; label: string; label2?: string }) {
  return (
    <Link href={href} aria-label={label} className="tap-link text-sm font-bold shrink-0" style={{ color: "var(--color-accent)" }}>
      {label2}
    </Link>
  );
}
