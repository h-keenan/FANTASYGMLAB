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

// "My Team", "Matchup", "Trade Hub", "Waivers", "League Rankings",
// "Alerts", "GM Plan", "GM Targets", "League Recaps / History", "Draft
// Center", "Trade Analyzer", "Players", and now "Live Draft" have real
// Next.js pages (see app/my-team/[leagueId], app/matchup/[leagueId],
// app/trade-hub/[leagueId], app/waivers/[leagueId],
// app/league-rankings/[leagueId], app/alerts/[leagueId],
// app/gm-plan/[leagueId], app/gm-targets/[leagueId],
// app/league-recaps/[leagueId], app/draft-center/[leagueId],
// app/trade-analyzer/[leagueId], app/players/[leagueId], and
// app/live-draft/[leagueId]) and are rendered separately below as internal
// <Link>s instead of Streamlit deep links — every other destination here
// (including Trade Finder) is still Streamlit-only for this revision.
//
// College Scouting (Revision 20) moved out of this Streamlit-deep-link
// quick-actions list and down into the Portfolio/News/Trade History group
// below: like those three, it has no [leagueId] segment (the shared
// prospect pool is identical regardless of which league is selected), so it
// isn't part of the per-league BUILT_PAGES loop either. No more quick
// actions remain, so the Streamlit-external-link rendering path they used
// is removed below too — everything in Explore is now a real page.
//
// Live Draft (Revision 21) is the last page on the original migration
// punch list — unlike every page above, it has no mobile reference screen
// (a real feature-parity gap, not an IA one; see LiveDraftContent.tsx's own
// docstring), so its two backing endpoints are new, not ports of an
// existing mobile endpoint.

const BUILT_PAGES: { label: string; path: string }[] = [
  { label: "My Team", path: "my-team" },
  { label: "Matchup", path: "matchup" },
  { label: "Trade Hub", path: "trade-hub" },
  { label: "Waivers", path: "waivers" },
  { label: "League Rankings", path: "league-rankings" },
  { label: "Alerts", path: "alerts" },
  { label: "GM Plan", path: "gm-plan" },
  { label: "GM Targets", path: "gm-targets" },
  { label: "League Recaps / History", path: "league-recaps" },
  { label: "Draft Center", path: "draft-center" },
  { label: "Trade Analyzer", path: "trade-analyzer" },
  { label: "Players", path: "players" },
  // Live Draft (Revision 21) — closes out the original migration punch
  // list. Shown unconditionally like every other entry here; the page
  // itself (not this nav) is what gates on an actual in-progress/paused
  // Sleeper draft, same as Streamlit's own route.
  { label: "Live Draft", path: "live-draft" },
];

// Portfolio (Revision 8) spans every saved league at once — unlike every
// entry above, its route (app/portfolio/page.tsx) takes no leagueId/name,
// so it isn't part of the per-league BUILT_PAGES loop below.

// One shared card style instead of six byte-identical inline style objects
// (Revision 7 CSS-cleanup pass — the five Explore cards this revision's
// Alerts card would otherwise have copied a sixth time).
const EXPLORE_CARD_STYLE = {
  background: "var(--color-surface-secondary)",
  border: "var(--border-width-default) solid var(--color-border)",
  color: "var(--color-text-primary)",
} as const;
const EXPLORE_CARD_CLASS = "px-4 py-3 text-sm font-bold flex items-center justify-between";

function ExploreCard({ href, label }: { href: string; label: string }) {
  return (
    <Link href={href} className={EXPLORE_CARD_CLASS} style={EXPLORE_CARD_STYLE}>
      {label}
      <span style={{ color: "var(--color-accent)" }}>→</span>
    </Link>
  );
}

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
              <GamePlanCard
                key={item.recommendation_id || item.headline}
                item={item}
                leagueId={leagueId}
                leagueName={leagueName}
              />
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
          Workflows ported to this app open here; everything else still opens in Streamlit.
        </p>
        <div className="grid grid-cols-2 gap-3">
          <ExploreCard href="/portfolio" label="Portfolio" />
          <ExploreCard href="/news" label="News" />
          <ExploreCard href="/trade-history" label="Trade History" />
          <ExploreCard href="/college-scouting" label="College Scouting" />
          {BUILT_PAGES.map((page) => (
            <ExploreCard
              key={page.path}
              href={`/${page.path}/${encodeURIComponent(leagueId)}?name=${encodeURIComponent(leagueName)}`}
              label={page.label}
            />
          ))}
        </div>
      </section>
    </main>
  );
}
