"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import {
  ApiError,
  api,
  type GuessThePlayerAnswerResponse,
  type GuessThePlayerCorrectIdentity,
  type GuessThePlayerOption,
  type GuessThePlayerResponse,
} from "@/lib/api";
import { PlayerAvatar } from "@/components/PlayerAvatar";
import { PositionBadge } from "@/components/PositionBadge";
import {
  getDismissedGuessThePlayerPickId,
  setDismissedGuessThePlayerPickId,
} from "@/lib/guessThePlayerDismissed";

/**
 * Dashboard mini-game (coridian_, 2026-10-19, confirmed spec via Discord):
 * "Whose stats are these?" — one real player's real recent week (stats
 * only, name/photo hidden), multiple-choice guess, then a reveal of the
 * real identity plus a real, persisted streak.
 *
 * Self-fetching (same pattern PlayerQuickView.tsx already uses) rather than
 * threaded through DashboardResponse: GET /v1/guess-the-player is
 * league-independent (one shared daily pick for every signed-in user), so
 * it doesn't belong on the per-league dashboard payload.
 *
 * "Dismissible" persists via lib/guessThePlayerDismissed.ts (coridian_,
 * 2026-10-19: "if you exit that module out, it shouldn't pop back up" — a
 * plain page-view-scoped useState used to reset on every fresh mount,
 * reappearing the moment someone navigated away and back). Same
 * pick_id-keyed localStorage shape mobile's own dismiss already uses, so a
 * new day's pick is never suppressed by a stale dismiss.
 */

type RevealState = {
  correct: boolean;
  correctPlayer: GuessThePlayerCorrectIdentity;
};

/** Exported so GuessThePlayerNameMatchCard.tsx — a separate daily
 * mini-game that shares this same "N in a row · Best M" streak shape —
 * can reuse the exact same copy/logic rather than inventing a second
 * version of it. */
export function streakCaption(streak: { current_streak: number; best_streak: number }): string {
  if (streak.current_streak <= 0 && streak.best_streak <= 0) return "Start a streak";
  const current = `${streak.current_streak} in a row`;
  if (streak.best_streak <= streak.current_streak) return current;
  return `${current} · Best ${streak.best_streak}`;
}

export function GuessThePlayerCard({
  leagueId,
  leagueName,
}: { leagueId?: string; leagueName?: string } = {}) {
  const [data, setData] = useState<GuessThePlayerResponse | null>(null);
  const [dismissedPickId, setDismissedPickId] = useState<string | null>(() => getDismissedGuessThePlayerPickId());
  const [selectedPlayerId, setSelectedPlayerId] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [reveal, setReveal] = useState<RevealState | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .getGuessThePlayer()
      .then((result) => {
        if (cancelled) return;
        setData(result);
        if (result.already_answered && result.correct_player) {
          setReveal({ correct: result.last_result === "correct", correctPlayer: result.correct_player });
          setSelectedPlayerId(result.correct_player.player_id);
        }
      })
      .catch(() => {
        // Silent on failure — this is a Dashboard extra, not core
        // functionality; the rest of the page must never block on it.
        if (!cancelled) setData(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (
    !data ||
    !data.available ||
    !data.prompt ||
    (dismissedPickId && dismissedPickId === data.prompt.pick_id)
  ) {
    return null;
  }
  const prompt = data.prompt;

  function dismiss() {
    setDismissedPickId(prompt.pick_id);
    setDismissedGuessThePlayerPickId(prompt.pick_id);
  }

  async function handleGuess(option: GuessThePlayerOption) {
    if (reveal || submitting || !prompt) return;
    setSelectedPlayerId(option.player_id);
    setSubmitting(true);
    setError(null);
    try {
      const result: GuessThePlayerAnswerResponse = await api.answerGuessThePlayer(prompt.pick_id, option.player_id);
      setReveal({ correct: result.correct, correctPlayer: result.correct_player });
      setData((previous) => (previous ? { ...previous, streak: result.streak, already_answered: true } : previous));
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 409) {
        // Today's pick rotated out from under this page view — refetch
        // rather than show a guess against stale data.
        setError("This round just ended — refreshing.");
        try {
          const refreshed = await api.getGuessThePlayer();
          setData(refreshed);
          setSelectedPlayerId(null);
          setError(null);
        } catch {
          setError("Could not refresh. Try again later.");
        }
      } else {
        setSelectedPlayerId(null);
        setError("Could not submit your guess. Try again.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <article className="glass-surface flex flex-col gap-3 p-4" data-testid="guess-the-player-card">
      <div className="flex items-start justify-between gap-2">
        <div className="flex flex-col gap-0.5">
          <span
            className="uppercase"
            style={{ font: "var(--type-badge-size)", letterSpacing: "var(--letter-spacing-badge)", color: "var(--color-accent)" }}
          >
            Guess the Player
          </span>
          <h3 style={{ font: "var(--font-card-title)" }}>Whose stats are these?</h3>
        </div>
        <button
          type="button"
          aria-label="Dismiss Guess the Player"
          onClick={dismiss}
          className="shrink-0 text-sm"
          style={{ color: "var(--color-text-muted)" }}
        >
          ✕
        </button>
      </div>

      <div className="flex items-center gap-3">
        <PlayerAvatar playerId={reveal ? reveal.correctPlayer.player_id : null} tier={prompt.tier} size={56} />
        <div className="flex flex-col gap-1">
          {reveal ? (
            <span className="font-bold">{reveal.correctPlayer.name}</span>
          ) : (
            <span className="font-bold" style={{ color: "var(--color-text-muted)" }}>
              ??? ???
            </span>
          )}
          <div className="flex items-center gap-2">
            <PositionBadge position={reveal ? reveal.correctPlayer.position : prompt.position} />
            {reveal ? <span className="text-xs" style={{ color: "var(--color-text-secondary)" }}>{reveal.correctPlayer.team}</span> : null}
            <span className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
              Week {prompt.week} · {prompt.season}
            </span>
          </div>
        </div>
      </div>

      <div className="flex flex-wrap gap-x-4 gap-y-1">
        {prompt.stat_line.map((item) => (
          <span key={item.label} className="text-sm">
            <strong>{item.value}</strong> <span style={{ color: "var(--color-text-secondary)" }}>{item.label}</span>
          </span>
        ))}
        <span className="text-sm">
          <strong>{prompt.fantasy_points_ppr}</strong> <span style={{ color: "var(--color-text-secondary)" }}>Fantasy Points (PPR)</span>
        </span>
      </div>

      <div className="flex flex-col gap-2" role="radiogroup" aria-label="Who is this player?">
        {prompt.options.map((option) => {
          const isSelected = selectedPlayerId === option.player_id;
          const isCorrectOption = reveal && option.player_id === reveal.correctPlayer.player_id;
          const isWrongSelection = reveal && isSelected && !isCorrectOption;
          let background = "var(--color-surface-raised)";
          let borderColor = "var(--color-border)";
          if (isCorrectOption) {
            background = "var(--color-success-soft)";
            borderColor = "var(--color-success)";
          } else if (isWrongSelection) {
            borderColor = "var(--color-danger)";
          } else if (isSelected) {
            borderColor = "var(--color-accent)";
          }
          return (
            <button
              key={option.player_id}
              type="button"
              role="radio"
              aria-checked={isSelected}
              disabled={Boolean(reveal) || submitting}
              onClick={() => handleGuess(option)}
              className="px-3 py-2 text-left text-sm font-bold"
              style={{
                background,
                border: `var(--border-width-default) solid ${borderColor}`,
                opacity: reveal && !isCorrectOption && !isWrongSelection ? 0.6 : 1,
              }}
            >
              {option.name}
            </button>
          );
        })}
      </div>

      {reveal ? (
        <p className="text-sm font-bold" style={{ color: reveal.correct ? "var(--color-success)" : "var(--color-danger)" }}>
          {reveal.correct ? "Correct!" : `Not quite — it was ${reveal.correctPlayer.name}.`}
        </p>
      ) : null}

      {error ? (
        <p className="text-sm" style={{ color: "var(--color-danger)" }}>
          {error}
        </p>
      ) : null}

      <div className="flex items-center justify-between gap-2">
        <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          {streakCaption(data.streak)}
        </p>
        {leagueId ? (
          <Link
            href={`/guess-the-player-leaderboard/${encodeURIComponent(leagueId)}${
              leagueName ? `?name=${encodeURIComponent(leagueName)}` : ""
            }`}
            className="text-xs font-bold shrink-0"
            style={{ color: "var(--color-accent)" }}
          >
            League Leaderboard →
          </Link>
        ) : null}
      </div>
    </article>
  );
}
