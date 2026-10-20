"use client";

import { useEffect, useState } from "react";

import { api, type GuessThePlayerLeaderboardEntry, type GuessThePlayerLeaderboardResponse } from "@/lib/api";

/**
 * League-scoped leaderboard across both Guess the Player mini-games' real,
 * persisted streaks (feature-brainstorm audit, coridian_ 2026-10-19, "do
 * it all"). Reachable from GuessThePlayerCard.tsx / GuessThePlayerNameMatchCard
 * .tsx's "League Leaderboard" link on Dashboard.
 *
 * Self-fetching (same pattern as the two Dashboard cards) rather than
 * threaded through a parent's data — this is its own standalone page, not
 * part of the Dashboard payload.
 *
 * "Leaguemates" here means the other FantasyDesk accounts that have this
 * SAME league saved, not every real Sleeper manager in the league (see
 * services/mobile_api_service.py's GET .../guess-the-player/leaderboard and
 * modules.guess_the_player_leaderboard's module docstring for exactly why)
 * — most real managers have no app account at all, so a league with real
 * data in Sleeper can still show an empty leaderboard here.
 */

type Mode = "stat_line" | "name_match";

const MODE_LABEL: Record<Mode, string> = {
  stat_line: "Whose Stats",
  name_match: "Who Is Who",
};

function LeaderboardRow({ entry }: { entry: GuessThePlayerLeaderboardEntry }) {
  return (
    <div
      className="flex items-center gap-3 py-2.5 px-1"
      style={{
        borderBottom: "var(--border-width-default) solid var(--color-border)",
        background: entry.is_viewer ? "var(--color-accent-soft)" : "transparent",
      }}
    >
      <span
        className="text-sm font-extrabold shrink-0 text-center"
        style={{ color: entry.rank === 1 ? "var(--color-premium)" : "var(--color-text-muted)", minWidth: "2.25rem" }}
      >
        {entry.rank}
      </span>
      <div className="flex-1 flex items-center gap-2 min-w-0">
        <span className="text-sm font-bold truncate" style={{ color: "var(--color-text-primary)" }}>
          {entry.display_name}
        </span>
        {entry.is_viewer ? (
          <span
            className="px-1.5 py-0.5 text-xs font-extrabold uppercase shrink-0"
            style={{
              background: "color-mix(in srgb, var(--color-success) 15%, transparent)",
              color: "var(--color-success)",
              border: "1px solid var(--color-success)",
            }}
          >
            You
          </span>
        ) : null}
      </div>
      <div className="flex flex-col items-end shrink-0">
        <span className="text-sm font-extrabold" style={{ color: "var(--color-text-primary)" }}>
          {entry.current_streak} <span className="font-normal" style={{ color: "var(--color-text-muted)" }}>streak</span>
        </span>
        <span className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
          Best {entry.best_streak}
        </span>
      </div>
    </div>
  );
}

export function GuessThePlayerLeaderboardContent({ leagueId }: { leagueId: string }) {
  const [data, setData] = useState<GuessThePlayerLeaderboardResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<Mode>("stat_line");

  useEffect(() => {
    let cancelled = false;
    api
      .getGuessThePlayerLeaderboard(leagueId)
      .then((result) => {
        if (!cancelled) setData(result);
      })
      .catch((caught) => {
        if (!cancelled) setError(caught instanceof Error ? caught.message : "Could not load the leaderboard.");
      });
    return () => {
      cancelled = true;
    };
  }, [leagueId]);

  if (!data && !error) {
    return (
      <main className="flex-1 flex items-center justify-center px-4 py-8" data-testid="guess-the-player-leaderboard-loading">
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
          Loading the leaderboard…
        </p>
      </main>
    );
  }

  if (error || !data) {
    return (
      <main className="flex-1 flex items-center justify-center px-4 py-8">
        <p role="alert" className="text-sm" style={{ color: "var(--color-danger)" }}>
          {error || "Could not load the leaderboard."}
        </p>
      </main>
    );
  }

  const entries = data[mode].entries;

  return (
    <main className="flex-1 flex flex-col gap-6 px-4 py-8 max-w-3xl w-full mx-auto">
      <header className="flex flex-col gap-2">
        <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          Guess the Player
        </span>
        <h1 style={{ font: "var(--font-page-title)" }}>League Leaderboard</h1>
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
          Real, persisted streaks among the other FantasyDesk users in this league — ranked by current streak, then
          best streak.
        </p>
      </header>

      <div className="flex gap-2" role="tablist" aria-label="Leaderboard game">
        {(Object.keys(MODE_LABEL) as Mode[]).map((key) => (
          <button
            key={key}
            type="button"
            role="tab"
            aria-selected={mode === key}
            onClick={() => setMode(key)}
            className="px-3 py-1.5 text-xs font-bold uppercase"
            style={{
              border: `var(--border-width-default) solid ${mode === key ? "var(--color-accent)" : "var(--color-border)"}`,
              color: mode === key ? "var(--color-accent)" : "var(--color-text-secondary)",
              background: mode === key ? "var(--color-accent-soft)" : "transparent",
            }}
          >
            {MODE_LABEL[key]}
          </button>
        ))}
      </div>

      {!data.configured ? (
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
          The leaderboard isn&apos;t available right now. Check back later.
        </p>
      ) : entries.length === 0 ? (
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
          Nobody else in this league has a FantasyDesk account yet. Invite your leaguemates to start a leaderboard.
        </p>
      ) : (
        <div className="flex flex-col" data-testid="guess-the-player-leaderboard-entries">
          {entries.map((entry) => (
            <LeaderboardRow key={entry.member_id} entry={entry} />
          ))}
        </div>
      )}
    </main>
  );
}
