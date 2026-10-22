"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { api, type LeagueTeamRankingsResponse, type TeamRanking } from "@/lib/api";
import { TeamAvatar } from "@/components/TeamAvatar";

/**
 * "League Pulse" Dashboard tile — named and deferred by DashboardContent.tsx's
 * own original port docstring ("League Pulse... needs either a new engine
 * endpoint beyond a thin wrapper or are Streamlit-session-state-shaped").
 * It doesn't need a new endpoint: GET .../team-rankings already carries real,
 * server-computed per-roster `transaction_activity_count` (modules.
 * manager_activity — actual completed trades/waiver claims/free-agent moves
 * this season) and `current_streak` (modules.team_streaks — actual
 * win/loss streak off real matchup results), the exact two signals this
 * tile needs. League Rankings' boards already surface the *classified*
 * version of this data (the "Highly Active"/"Quiet Manager"/"Hot Streak"/
 * "Cold Streak" team_badges), but only for teams extreme enough to cross a
 * badge threshold — most leagues' real activity/streak leaders never had
 * anywhere to show the real number. This tile is that: a small, league-wide
 * highlight (not a full board — League Rankings is still the place for
 * every team's own row) naming the actual league-wide leader in each real
 * signal with the Real plain number attached.
 *
 * Self-fetching, same contract as GuessThePlayerCard/
 * GuessThePlayerNameMatchCard above it on the Dashboard: this is enrichment,
 * not core content, so a fetch failure or a quiet league with no standout
 * signal yet (common early season, before enough transactions/streaks have
 * accumulated) just renders nothing rather than disrupting the real Game
 * Plan content below it with an error banner or a hollow "nothing here"
 * message.
 */

type Highlight = {
  key: string;
  label: string;
  tone: "positive" | "negative" | "neutral";
  team: TeamRanking;
  metric: string;
};

function mostActiveHighlight(teams: TeamRanking[]): Highlight | null {
  if (teams.length === 0) return null;
  const leader = teams.reduce((best, team) =>
    (team.transaction_activity_count ?? 0) > (best.transaction_activity_count ?? 0) ? team : best,
  );
  const count = leader.transaction_activity_count ?? 0;
  if (count <= 0) return null;
  return {
    key: "most-active",
    label: "Most Active Manager",
    tone: "neutral",
    team: leader,
    metric: `${count} move${count === 1 ? "" : "s"}`,
  };
}

function hotStreakHighlight(teams: TeamRanking[]): Highlight | null {
  const candidates = teams.filter((team) => (team.current_streak ?? 0) >= 2);
  if (candidates.length === 0) return null;
  const leader = candidates.reduce((best, team) => (team.current_streak > best.current_streak ? team : best));
  return { key: "hot-streak", label: "Hot Streak", tone: "positive", team: leader, metric: `W${leader.current_streak}` };
}

function coldStreakHighlight(teams: TeamRanking[]): Highlight | null {
  const candidates = teams.filter((team) => (team.current_streak ?? 0) <= -2);
  if (candidates.length === 0) return null;
  const leader = candidates.reduce((worst, team) => (team.current_streak < worst.current_streak ? team : worst));
  return {
    key: "cold-streak",
    label: "Cold Streak",
    tone: "negative",
    team: leader,
    metric: `L${Math.abs(leader.current_streak)}`,
  };
}

/** Exported for tests — pure derivation of this tile's highlights from an
 * already-fetched team list, same split other presentation helpers in this
 * app use between "compute" and "render". */
export function leaguePulseHighlights(teams: TeamRanking[]): Highlight[] {
  return [mostActiveHighlight(teams), hotStreakHighlight(teams), coldStreakHighlight(teams)].filter(
    (highlight): highlight is Highlight => highlight !== null,
  );
}

function toneColor(tone: Highlight["tone"]): string {
  if (tone === "positive") return "var(--color-success)";
  if (tone === "negative") return "var(--color-danger)";
  return "var(--color-text-muted)";
}

export function LeaguePulseCard({
  leagueId,
  leagueName = "",
  teamRankings,
}: {
  leagueId: string;
  leagueName?: string;
  /** Already-started GET .../team-rankings for this league (the Dashboard page
   * starts it alongside its own request). Omitted: fetch it here. */
  teamRankings?: Promise<LeagueTeamRankingsResponse>;
}) {
  const [highlights, setHighlights] = useState<Highlight[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    (teamRankings ?? api.getTeamRankings(leagueId))
      .then((result) => {
        if (cancelled) return;
        setHighlights(result.ok ? leaguePulseHighlights(result.teams) : []);
      })
      .catch(() => {
        // Silent on failure — a Dashboard extra, not core functionality;
        // the rest of the page must never block or visually disrupt on it.
        if (!cancelled) setHighlights([]);
      });
    return () => {
      cancelled = true;
    };
  }, [leagueId, teamRankings]);

  if (!highlights || highlights.length === 0) return null;

  return (
    <article className="glass-surface flex flex-col gap-3 p-4" data-testid="league-pulse-card">
      <div className="flex items-center justify-between gap-2">
        <h3 style={{ font: "var(--font-card-title)" }}>League Activity</h3>
        <Link
          href={`/league-recaps/${encodeURIComponent(leagueId)}${leagueName ? `?name=${encodeURIComponent(leagueName)}` : ""}`}
          aria-label="Open League Recaps"
          style={{ color: "var(--color-accent)" }}
        >
          ›
        </Link>
      </div>
      <div className="flex flex-col gap-2.5">
        {highlights.map((highlight) => (
          <div key={highlight.key} className="flex items-center gap-3">
            <TeamAvatar avatarUrl={highlight.team.avatar_url} size={28} />
            <div className="flex-1 flex flex-col min-w-0">
              <span
                className="uppercase"
                style={{ font: "var(--type-supporting-metadata)", letterSpacing: "var(--letter-spacing-badge)", color: toneColor(highlight.tone) }}
              >
                {highlight.label}
              </span>
              <span className="text-sm font-bold truncate" style={{ color: "var(--color-text-primary)" }}>
                {highlight.team.team_name || "Team"}
              </span>
            </div>
            <span className="text-sm font-extrabold shrink-0" style={{ color: toneColor(highlight.tone) }}>
              {highlight.metric}
            </span>
          </div>
        ))}
      </div>
    </article>
  );
}
