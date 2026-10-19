import Link from "next/link";

import type { DashboardResponse } from "@/lib/api";
import { GamePlanCard } from "@/components/GamePlanCard";
import { SnapshotTile, formatRank } from "@/components/SnapshotTile";
import { WatchListCard } from "@/components/WatchListCard";
import { notReadyReasonMessage } from "@/lib/notReadyMessages";

/**
 * Ports modules/dashboard_workflow.py's render_dashboard_workflow for
 * Revision 1 (see PR description for exactly what's deferred: What
 * Changed, League Pulse, roster-aware News Alert tiles, league recap
 * teaser, orientation tour, startup-mode/ESPN-degraded variants — all of
 * those need either a new engine endpoint beyond a thin wrapper or are
 * Streamlit-session-state-shaped and aren't core to this milestone).
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
}: {
  leagueId: string;
  leagueName: string;
  data: DashboardResponse;
}) {
  const snapshot = data.team_snapshot;

  return (
    // coridian_, 2026-10-17 (screenshot): too much empty space above the
    // first real card on Dashboard — the one page most people land on
    // first. Tighter top padding/section gap than the other pages' shared
    // shell (gap-8 px-4 py-8) and the "Today's Game Plan" subtitle dropped
    // (it only restated what the heading already said; the real content —
    // the actionable cards below — is what should hit the fold).
    <main className="flex-1 flex flex-col gap-6 px-4 py-5 max-w-3xl w-full mx-auto">
      {/* coridian_, 2026-10-18: "dashboard should go up into the header...
          so you can always see what page you're on" — the "Dashboard"
          label now lives in the persistent Header (HeaderPageTitle) instead
          of repeated here, where it scrolls away with the rest of the page.
          The league name stays as this page's own <h1> — normal page
          content, not something he asked to remove — it's ALSO now in the
          header's league switcher button. */}
      <header className="flex flex-col gap-1">
        <h1 style={{ font: "var(--font-page-title)" }}>{leagueName}</h1>
      </header>

      <section className="flex flex-col gap-3" aria-labelledby="game-plan-heading" data-fgl-dashboard-useful="true">
        <h2 id="game-plan-heading" style={{ font: "var(--type-section-title)" }}>
          Today&apos;s Game Plan
        </h2>

        {data.quiet || data.items.length === 0 ? (
          <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
            {/* Zach's repro: a league still mid-draft resolves to an empty
                roster (Sleeper doesn't populate roster.players until the
                draft completes), which previously crashed this page
                entirely (see services/mobile_api_service.py's
                get_league_dashboard fix). Now that it returns cleanly,
                this reason deserves a message that actually explains why,
                not the generic "no urgent issues" line. */}
            {notReadyReasonMessage(data.reason, {
              linkAccount: "Connect your Sleeper account to see your Game Plan.",
              emptyRoster: "Your roster doesn't have any players yet — this is expected if your draft is still in progress.",
            }) || "No urgent roster issues right now."}
          </p>
        ) : (
          <div className="flex flex-col gap-3">
            {/* coridian_, 2026-10-18: "you can just put them all under
                watch... to make this much simpler and more streamlined" —
                Top Priority keeps its own full card (it's the single
                highest-priority recommendation); every other item groups
                into one WatchListCard instead of each getting a full card
                of its own. */}
            {data.items
              .filter((item) => item.category === "top_priority")
              .map((item) => (
                <GamePlanCard
                  key={item.recommendation_id || item.headline}
                  item={item}
                  leagueId={leagueId}
                  leagueName={leagueName}
                />
              ))}
            <WatchListCard
              items={data.items.filter((item) => item.category !== "top_priority")}
              leagueId={leagueId}
              leagueName={leagueName}
            />
          </div>
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

      {snapshot ? (
        <section className="flex flex-col gap-3" aria-labelledby="snapshot-heading" data-fgl-dashboard-complete="true">
          <h2 id="snapshot-heading" style={{ font: "var(--type-section-title)" }}>
            Team Snapshot
          </h2>
          <div className="flex flex-wrap gap-3">
            <SnapshotTile
              glyph="record"
              label="Record"
              value={`${snapshot.wins ?? 0}-${snapshot.losses ?? 0}${snapshot.ties ? `-${snapshot.ties}` : ""}`}
            />
            <SnapshotTile
              glyph="power"
              label="Power Rank"
              value={formatRank(snapshot.power_rank, snapshot.power_rank_tied)}
              tone={snapshot.power_rank === 1 ? "premium" : "neutral"}
            />
            <SnapshotTile
              glyph="franchise"
              label="Franchise Rank"
              value={formatRank(snapshot.franchise_rank, snapshot.franchise_rank_tied)}
              tone={snapshot.franchise_rank === 1 ? "premium" : "neutral"}
            />
            <SnapshotTile
              glyph="starter"
              label="Starter Strength"
              value={formatRank(snapshot.starter_rank, snapshot.starter_rank_tied)}
              tone={snapshot.starter_rank === 1 ? "premium" : "neutral"}
            />
            <SnapshotTile
              glyph="bench"
              label="Bench Strength"
              value={formatRank(snapshot.bench_rank, snapshot.bench_rank_tied)}
              tone={snapshot.bench_rank === 1 ? "premium" : "neutral"}
            />
            <SnapshotTile
              glyph="age"
              label="Avg Age"
              value={snapshot.average_age !== null ? snapshot.average_age.toFixed(1) : "—"}
            />
            <SnapshotTile
              glyph="injury"
              label="Injuries"
              value={snapshot.health_flag || "Stable"}
              tone={snapshot.injured_starters && snapshot.injured_starters > 0 ? "risk" : "positive"}
            />
          </div>
        </section>
      ) : null}

      {/* Explore grid removed entirely (coridian_, 2026-10-18: "You never
          removed the explore section"). The 2026-10-17 pass only hid it at
          md+ width, reasoning GmOrb was "a floating button, not a
          persistent nav" on mobile — but GmOrb (fixed bottom-center on
          every mobile page, see GmOrb.tsx) already surfaces this exact
          same League/GM Tools/General destination list via
          useNavDestinations, so the grid was genuinely redundant on mobile
          too, not just desktop. */}
    </main>
  );
}
