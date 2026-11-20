"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { api, type LeagueMatchupsResponse } from "@/lib/api";
import { dataAgeSeconds, nextPollDelayMs, shouldPoll } from "@/lib/liveScores";
import { useLatestGate } from "@/lib/useLatestGate";

/**
 * Loads the league-wide matchups list for one week and, only while the server says NFL games are live, keeps it fresh with the
 * same rules as useLiveMatchup (30-60 s while visible and online, paused when hidden, exponential back-off, last good data kept on a
 * failed refresh). `week` null asks for the league's current week. A week change retires the old request.
 */
export function useLeagueMatchups(leagueId: string, week: number | null, enabled = true) {
  const [data, setData] = useState<LeagueMatchupsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [receivedAt, setReceivedAt] = useState<number | null>(null);
  const [now, setNow] = useState(() => Date.now());
  const failures = useRef(0);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const latest = useRef<LeagueMatchupsResponse | null>(null);
  const cancelled = useRef(false);
  const gate = useLatestGate();
  const reload = useRef<() => void>(() => {});

  const clearTimer = () => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = null;
  };
  const visibleAndOnline = () =>
    (typeof document === "undefined" || document.visibilityState !== "hidden") &&
    (typeof navigator === "undefined" || navigator.onLine !== false);

  const load = useCallback(async () => {
    const isCurrent = gate.begin();
    let retryAfter: number | undefined;
    try {
      const result = await api.getLeagueMatchups(leagueId, week);
      if (cancelled.current || !isCurrent()) return;
      failures.current = 0;
      latest.current = result;
      setData(result);
      setReceivedAt(Date.now());
      setError(null);
    } catch (err) {
      if (cancelled.current || !isCurrent()) return;
      failures.current += 1;
      retryAfter = (err as { retryAfterSeconds?: number } | null)?.retryAfterSeconds;
      if (!latest.current) setError(err instanceof Error ? err.message : "Could not load matchups.");
    } finally {
      if (!cancelled.current && isCurrent()) {
        clearTimer();
        const current = latest.current;
        if (current && shouldPoll({ live: current.live === true, pollAfterSeconds: current.poll_after_seconds, visible: visibleAndOnline(), online: true })) {
          timer.current = setTimeout(() => reload.current(), nextPollDelayMs(current.poll_after_seconds, failures.current, retryAfter));
        }
      }
    }
  }, [gate, leagueId, week]);

  useEffect(() => {
    if (!enabled) return;
    cancelled.current = false;
    failures.current = 0;
    latest.current = null;
    reload.current = () => void load();
    // Subscribing to an external system (the API poll); its callbacks set state, not this effect body.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
    const onVisibility = () => {
      if (document.visibilityState === "hidden") return clearTimer();
      if (latest.current?.live === true) void load();
    };
    const tick = setInterval(() => setNow(Date.now()), 5_000);
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      cancelled.current = true;
      gate.cancel();
      clearTimer();
      clearInterval(tick);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [enabled, gate, load]);

  const ageSeconds = data && receivedAt != null && data.as_of_age_seconds != null ? dataAgeSeconds(data.as_of_age_seconds, receivedAt, now) : null;
  // A different week is on its way: the last list stays up, dimmed, until it lands.
  const loading = data != null && week != null && data.week !== week;
  return { data, error, loading, ageSeconds };
}
