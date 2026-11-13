"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { api, type MatchupResponse } from "@/lib/api";
import { dataAgeSeconds, nextPollDelayMs, shouldPoll } from "@/lib/liveScores";

/**
 * Loads the Matchup payload and, only while the server says NFL games are live
 * (`live` / `poll_after_seconds`), keeps it fresh: refresh every 30-60 s while
 * the tab is visible and online, pause when hidden/offline (and catch up the
 * moment it is visible again), back off exponentially on errors, and expose a
 * manual refresh. A failed refresh keeps the last good data on screen.
 */
export function useLiveMatchup(leagueId: string, lens: string, enabled: boolean) {
  const [matchup, setMatchup] = useState<MatchupResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [receivedAt, setReceivedAt] = useState<number | null>(null);
  const [now, setNow] = useState(() => Date.now());
  const failures = useRef(0);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const latest = useRef<MatchupResponse | null>(null);
  const inFlight = useRef(false);
  const cancelled = useRef(false);

  const clearTimer = () => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = null;
  };

  const visibleAndOnline = () =>
    (typeof document === "undefined" || document.visibilityState !== "hidden") &&
    (typeof navigator === "undefined" || navigator.onLine !== false);

  const schedule = useCallback((load: () => void, retryAfter?: number) => {
    clearTimer();
    const current = latest.current;
    if (cancelled.current || !current) return;
    if (!shouldPoll({ live: current.live === true, pollAfterSeconds: current.poll_after_seconds, visible: visibleAndOnline(), online: true })) {
      return; // resumed by the visibility/online listeners below
    }
    timer.current = setTimeout(load, nextPollDelayMs(current.poll_after_seconds, failures.current, retryAfter));
  }, []);

  const load = useCallback(
    async (manual = false) => {
      if (inFlight.current) return;
      inFlight.current = true;
      if (manual) setRefreshing(true);
      let retryAfter: number | undefined;
      try {
        const result = await api.getLeagueMatchup(leagueId, lens);
        if (cancelled.current) return;
        failures.current = 0;
        latest.current = result;
        setMatchup(result);
        setReceivedAt(Date.now());
        setError(null);
      } catch (err) {
        if (cancelled.current) return;
        failures.current += 1;
        retryAfter = (err as { retryAfterSeconds?: number } | null)?.retryAfterSeconds;
        // Keep showing the last good payload; only a first-load failure is an error screen.
        if (!latest.current) setError(err instanceof Error ? err.message : "Could not load this week's matchup.");
      } finally {
        inFlight.current = false;
        if (!cancelled.current) {
          setRefreshing(false);
          schedule(() => void load(), retryAfter);
        }
      }
    },
    [leagueId, lens, schedule],
  );

  useEffect(() => {
    if (!enabled) return;
    cancelled.current = false;
    failures.current = 0;
    latest.current = null;
    void load();
    const onVisibility = () => {
      if (document.visibilityState === "hidden") return clearTimer();
      const current = latest.current;
      if (current?.live === true) void load(); // catch up right away
    };
    const onOnline = () => {
      if (latest.current?.live === true) void load();
    };
    const onOffline = () => clearTimer();
    const tick = setInterval(() => setNow(Date.now()), 5_000);
    document.addEventListener("visibilitychange", onVisibility);
    window.addEventListener("online", onOnline);
    window.addEventListener("offline", onOffline);
    return () => {
      cancelled.current = true;
      clearTimer();
      clearInterval(tick);
      document.removeEventListener("visibilitychange", onVisibility);
      window.removeEventListener("online", onOnline);
      window.removeEventListener("offline", onOffline);
    };
  }, [enabled, load]);

  const ageSeconds =
    matchup && receivedAt != null && matchup.as_of_age_seconds != null
      ? dataAgeSeconds(matchup.as_of_age_seconds, receivedAt, now)
      : null;

  return { matchup, error, refreshing, ageSeconds, refresh: () => void load(true) };
}
