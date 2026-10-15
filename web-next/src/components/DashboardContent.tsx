import Link from "next/link";

import type { DashboardResponse } from "@/lib/api";
import { GamePlanCard } from "@/components/GamePlanCard";
import { SnapshotTile, formatRank } from "@/components/SnapshotTile";
import { streamlitPageUrl } from "@/lib/streamlitLink";

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

// "My Team" now has a real Next.js page (see app/my-team/[leagueId]) and is
// rendered separately below as an internal <Link> instead of a Streamlit
// deep link — every other destination here is still Streamlit-only for
// this revision.
const QUICK_ACTIONS: { label: string; destination: string }[] = [
  { label: "League Overview", destination: "rankings" },
  { label: "Trade Hub", destination: "trade_hub" },
  { label: "Waivers", destination: "waivers" },
  { label: "Draft Center", destination: "draft_summary" },
  { label: "GM Plan", destination: "gm_plan" },
  { label: "Trade History", destination: "trade_history" },
  { label: "College Scouting", destination: "college_scouting" },
];

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
    <main className="flex-1 flex flex-col gap-8 px-4 py-8 max-w-3xl w-full mx-auto">
      <header className="flex flex-col gap-1">
        <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          Dashboard
        </span>
        <h1 style={{ font: "var(--font-page-title)" }}>{leagueName}</h1>
      </header>

      <section className="flex flex-col gap-3" aria-labelledby="game-plan-heading" data-fgl-dashboard-useful="true">
        <h2 id="game-plan-heading" style={{ font: "var(--type-section-title)" }}>
          Today&apos;s Game Plan
        </h2>
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
          Your highest-impact moves right now.
        </p>

        {data.quiet || data.items.length === 0 ? (
          <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
            No urgent roster issues right now.
          </p>
        ) : (
          <div className="flex flex-col gap-3">
            {data.items.map((item) => (
              <GamePlanCard key={item.recommendation_id || item.headline} item={item} />
            ))}
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
            <a href={streamlitPageUrl("premium")} className="text-sm font-bold self-start" style={{ color: "var(--color-premium)" }}>
              Upgrade →
            </a>
          </div>
        ) : null}
      </section>

      {snapshot ? (
        <section className="flex flex-col gap-3" aria-labelledby="snapshot-heading" data-fgl-dashboard-complete="true">
          <h2 id="snapshot-heading" style={{ font: "var(--type-section-title)" }}>
            Team Snapshot
          </h2>
          <div className="flex flex-wrap gap-3">
            <SnapshotTile label="Record" value={`${snapshot.wins ?? 0}-${snapshot.losses ?? 0}${snapshot.ties ? `-${snapshot.ties}` : ""}`} />
            <SnapshotTile label="Power Rank" value={formatRank(snapshot.power_rank, snapshot.power_rank_tied)} />
            <SnapshotTile label="Franchise Rank" value={formatRank(snapshot.franchise_rank, snapshot.franchise_rank_tied)} />
            <SnapshotTile label="Starter Strength" value={formatRank(snapshot.starter_rank, snapshot.starter_rank_tied)} />
            <SnapshotTile label="Bench Strength" value={formatRank(snapshot.bench_rank, snapshot.bench_rank_tied)} />
            <SnapshotTile
              label="Avg Age"
              value={snapshot.average_age !== null ? snapshot.average_age.toFixed(1) : "—"}
            />
            <SnapshotTile
              label="Injuries"
              value={snapshot.health_flag || "Stable"}
              tone={snapshot.injured_starters && snapshot.injured_starters > 0 ? "risk" : "positive"}
            />
          </div>
        </section>
      ) : null}

      <section className="flex flex-col gap-3" aria-labelledby="explore-heading">
        <h2 id="explore-heading" style={{ font: "var(--type-section-title)" }}>
          Explore
        </h2>
        <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          Still in Streamlit for this release — opens in the existing app.
        </p>
        <div className="grid grid-cols-2 gap-3">
          <Link
            href={`/my-team/${encodeURIComponent(leagueId)}?name=${encodeURIComponent(leagueName)}`}
            className="px-4 py-3 text-sm font-bold flex items-center justify-between"
            style={{
              background: "var(--color-surface-secondary)",
              border: "var(--border-width-default) solid var(--color-border)",
              color: "var(--color-text-primary)",
            }}
          >
            My Team
            <span style={{ color: "var(--color-accent)" }}>→</span>
          </Link>
          {QUICK_ACTIONS.map((action) => (
            <a
              key={action.destination}
              href={streamlitPageUrl(action.destination)}
              className="px-4 py-3 text-sm font-bold flex items-center justify-between"
              style={{
                background: "var(--color-surface-secondary)",
                border: "var(--border-width-default) solid var(--color-border)",
                color: "var(--color-text-primary)",
              }}
            >
              {action.label}
              <span style={{ color: "var(--color-accent)" }}>→</span>
            </a>
          ))}
        </div>
      </section>
    </main>
  );
}
