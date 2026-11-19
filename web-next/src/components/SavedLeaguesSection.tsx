"use client";

import { useEffect, useState } from "react";

import { Button } from "@/components/Button";
import { ErrorState } from "@/components/ErrorState";
import { api } from "@/lib/api";
import { supabase } from "@/lib/supabase";

type SavedLeague = { league_id: string; league_name: string | null };

/**
 * Account's "Saved leagues" list with removal. Uses the same saved_leagues
 * read as FreeLeagueLimitNote and the same api.removeSavedLeague as
 * Portfolio, but is reachable on every plan (Portfolio is Pro-only, so a
 * Free user who saved the wrong league had no way to swap it). Mirrors
 * mobile's More > Saved leagues. Renders nothing until leagues load, and
 * when there are none; a failed read shows a retry row instead.
 */
export function SavedLeaguesSection() {
  const [leagues, setLeagues] = useState<SavedLeague[]>([]);
  const [confirmingId, setConfirmingId] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  // A failed read must not look like "no saved leagues" (the section would vanish and the user could not remove a wrong one).
  const [loadFailed, setLoadFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    Promise.resolve(supabase.from("saved_leagues").select("league_id, league_name").order("is_default", { ascending: false }))
      .then(({ data, error: readError }) => {
        if (cancelled) return;
        if (readError || !data) {
          setLoadFailed(true);
          return;
        }
        setLoadFailed(false);
        setLeagues(data as SavedLeague[]);
      })
      .catch(() => {
        if (!cancelled) setLoadFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, [attempt]);

  const remove = (leagueId: string) => {
    setBusyId(leagueId);
    setError(null);
    api
      .removeSavedLeague(leagueId)
      .then((result) => {
        if (result.ok) {
          setLeagues((prev) => prev.filter((league) => league.league_id !== leagueId));
          setConfirmingId(null);
        } else {
          setError("Could not remove that league right now. Please try again in a moment.");
        }
      })
      .catch(() => setError("Could not remove that league right now. Please try again in a moment."))
      .finally(() => setBusyId(null));
  };

  if (loadFailed && leagues.length === 0) return <ErrorState compact onRetry={() => setAttempt((n) => n + 1)} message="Could not load your saved leagues" />;
  if (leagues.length === 0) return null;

  return (
    <section className="glass-surface p-4 flex flex-col gap-3" aria-labelledby="account-saved-leagues-heading">
      <h2
        id="account-saved-leagues-heading"
        className="text-xs font-bold uppercase"
        style={{ color: "var(--color-text-muted)", letterSpacing: "0.03em" }}
      >
        Saved leagues
      </h2>
      {error ? (
        <p role="alert" className="text-xs" style={{ color: "var(--color-danger)" }}>
          {error}
        </p>
      ) : null}
      <ul className="flex flex-col gap-2">
        {leagues.map((league) => (
          <li key={league.league_id} className="flex flex-col gap-2">
            <div className="flex items-center justify-between gap-3 text-sm">
              <span className="font-semibold min-w-0 break-words">{league.league_name || league.league_id}</span>
              {confirmingId === league.league_id ? null : (
                <button
                  type="button"
                  onClick={() => setConfirmingId(league.league_id)}
                  className="text-xs font-bold text-right min-h-[var(--touch-target-min)]"
                  style={{ color: "var(--color-text-muted)" }}
                >
                  Not your league? Remove
                </button>
              )}
            </div>
            {confirmingId === league.league_id ? (
              <div className="flex flex-col gap-2">
                <p className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
                  Remove this league from your saved leagues? You can add it again later.
                </p>
                <div className="flex items-center gap-2">
                  <Button variant="danger" size="sm" loading={busyId === league.league_id} onClick={() => remove(league.league_id)}>
                    {busyId === league.league_id ? "Removing…" : "Confirm remove"}
                  </Button>
                  <Button variant="secondary" size="sm" disabled={busyId === league.league_id} onClick={() => setConfirmingId(null)}>
                    Cancel
                  </Button>
                </div>
              </div>
            ) : null}
          </li>
        ))}
      </ul>
    </section>
  );
}
