"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import {
  ApiError,
  api,
  type GuessThePlayerNameMatchAnswerResponse,
  type GuessThePlayerNameMatchCorrectPairing,
  type GuessThePlayerNameMatchResponse,
} from "@/lib/api";
import { PlayerAvatar } from "@/components/PlayerAvatar";
import { PositionBadge } from "@/components/PositionBadge";
import { streakCaption } from "@/components/GuessThePlayerCard";
import {
  getDismissedGuessThePlayerNameMatchPickId,
  setDismissedGuessThePlayerNameMatchPickId,
} from "@/lib/guessThePlayerNameMatchDismissed";

/**
 * "Who is who?" — a SECOND, distinct Dashboard mini-game alongside
 * GuessThePlayerCard.tsx (coridian_, 2026-10-19, same Discord thread):
 * "you get two players and one player is, you know, a known name that's
 * good, and then one player is kind of an unknown name who maybe has
 * better stats than the known name, and so you pick and choose who is
 * who." Unlike Guess the Player, BOTH players' real identity is shown up
 * front — what's hidden is which of the two real, unlabeled stat lines
 * belongs to which player. Tapping a stat line guesses which slot is the
 * famous player's.
 *
 * Self-fetching (same pattern GuessThePlayerCard.tsx already uses) — GET
 * /v1/guess-the-player/name-match is league-independent, so it doesn't
 * belong on the per-league dashboard payload.
 *
 * "Dismissible" persists via lib/guessThePlayerNameMatchDismissed.ts, the
 * SAME pick_id-keyed localStorage shape GuessThePlayerCard.tsx's dismiss
 * uses (and the real fix that shipped for it earlier today — built in
 * from the start here), but under its own distinct storage key so a
 * dismiss of one game's card can never suppress the other's.
 */

type RevealState = {
  correct: boolean;
  correctPairing: GuessThePlayerNameMatchCorrectPairing;
};

export function GuessThePlayerNameMatchCard({ leagueId }: { leagueId?: string } = {}) {
  const [data, setData] = useState<GuessThePlayerNameMatchResponse | null>(null);
  const [dismissedPickId, setDismissedPickId] = useState<string | null>(() =>
    getDismissedGuessThePlayerNameMatchPickId(),
  );
  const [selectedSlot, setSelectedSlot] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [reveal, setReveal] = useState<RevealState | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .getGuessThePlayerNameMatch()
      .then((result) => {
        if (cancelled) return;
        setData(result);
        if (result.already_answered && result.correct_pairing) {
          setReveal({
            correct: result.last_result === "correct",
            correctPairing: result.correct_pairing,
          });
          setSelectedSlot(result.correct_pairing.famous_slot);
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
  const slotEntries = Object.entries(prompt.slots).sort(([a], [b]) => a.localeCompare(b));

  function dismiss() {
    setDismissedPickId(prompt.pick_id);
    setDismissedGuessThePlayerNameMatchPickId(prompt.pick_id);
  }

  async function handleGuess(slot: string) {
    if (reveal || submitting || !prompt) return;
    setSelectedSlot(slot);
    setSubmitting(true);
    setError(null);
    try {
      const result: GuessThePlayerNameMatchAnswerResponse = await api.answerGuessThePlayerNameMatch(
        prompt.pick_id,
        slot,
      );
      setReveal({ correct: result.correct, correctPairing: result.correct_pairing });
      setData((previous) => (previous ? { ...previous, streak: result.streak, already_answered: true } : previous));
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 409) {
        // Today's pairing rotated out from under this page view —
        // refetch rather than show a guess against stale data.
        setError("This round just ended — refreshing.");
        try {
          const refreshed = await api.getGuessThePlayerNameMatch();
          setData(refreshed);
          setSelectedSlot(null);
          setError(null);
        } catch {
          setError("Could not refresh. Try again later.");
        }
      } else {
        setSelectedSlot(null);
        setError("Could not submit your guess. Try again.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <article className="glass-surface flex flex-col gap-3 p-4" data-testid="guess-the-player-name-match-card">
      <div className="flex items-start justify-between gap-2">
        <div className="flex flex-col gap-0.5">
          <span
            className="uppercase"
            style={{ font: "var(--type-badge-size)", letterSpacing: "var(--letter-spacing-badge)", color: "var(--color-accent)" }}
          >
            Name Match
          </span>
          <h3 style={{ font: "var(--font-card-title)" }}>Who Is Who?</h3>
        </div>
        <button
          type="button"
          aria-label="Dismiss Name Match"
          onClick={dismiss}
          className="shrink-0 text-sm"
          style={{ color: "var(--color-text-muted)" }}
        >
          ✕
        </button>
      </div>

      <div className="flex flex-wrap gap-3">
        {[
          { identity: prompt.famous_player, kicker: "Known Name" },
          { identity: prompt.obscure_player, kicker: "Unknown Name" },
        ].map(({ identity, kicker }) => (
          <div key={identity.player_id} className="flex flex-1 items-center gap-2" style={{ minWidth: "140px" }}>
            <PlayerAvatar playerId={identity.player_id} tier={identity.tier} size={48} />
            <div className="flex flex-col gap-0.5">
              <span className="text-xs uppercase" style={{ color: "var(--color-text-muted)" }}>
                {kicker}
              </span>
              <span className="font-bold">{identity.name}</span>
              <div className="flex items-center gap-2">
                <PositionBadge position={identity.position} />
                <span className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
                  {identity.team}
                </span>
              </div>
            </div>
          </div>
        ))}
      </div>

      <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
        Which stat line belongs to <strong>{prompt.famous_player.name}</strong>? Week {prompt.week} · {prompt.season}
      </p>

      <div className="flex flex-col gap-2" role="radiogroup" aria-label={`Which stat line belongs to ${prompt.famous_player.name}?`}>
        {slotEntries.map(([slot, payload]) => {
          const isSelected = selectedSlot === slot;
          const isCorrectSlot = reveal && slot === reveal.correctPairing.famous_slot;
          const isWrongSelection = reveal && isSelected && !isCorrectSlot;
          let background = "var(--color-surface-raised)";
          let borderColor = "var(--color-border)";
          if (isCorrectSlot) {
            background = "var(--color-success-soft)";
            borderColor = "var(--color-success)";
          } else if (isWrongSelection) {
            borderColor = "var(--color-danger)";
          } else if (isSelected) {
            borderColor = "var(--color-accent)";
          }
          return (
            <button
              key={slot}
              type="button"
              role="radio"
              aria-checked={isSelected}
              disabled={Boolean(reveal) || submitting}
              onClick={() => handleGuess(slot)}
              className="flex flex-col gap-1 px-3 py-2 text-left text-sm"
              style={{
                background,
                border: `var(--border-width-default) solid ${borderColor}`,
                opacity: reveal && !isCorrectSlot && !isWrongSelection ? 0.6 : 1,
              }}
            >
              <span className="text-xs font-bold uppercase" style={{ color: "var(--color-text-muted)" }}>
                Stat Line {slot}
              </span>
              <div className="flex flex-wrap gap-x-4 gap-y-1">
                {payload.stat_line.map((item) => (
                  <span key={item.label}>
                    <strong>{item.value}</strong> <span style={{ color: "var(--color-text-secondary)" }}>{item.label}</span>
                  </span>
                ))}
                <span>
                  <strong>{payload.fantasy_points_ppr}</strong>{" "}
                  <span style={{ color: "var(--color-text-secondary)" }}>Fantasy Points (PPR)</span>
                </span>
              </div>
            </button>
          );
        })}
      </div>

      {reveal ? (
        <p className="text-sm font-bold" style={{ color: reveal.correct ? "var(--color-success)" : "var(--color-danger)" }}>
          {reveal.correct ? "Correct!" : "Not quite."} The lesser-known name actually had the better week!
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
            href={`/guess-the-player-leaderboard/${encodeURIComponent(leagueId)}`}
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
