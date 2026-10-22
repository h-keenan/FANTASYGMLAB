"use client";

import { useEffect, useRef, useState } from "react";

import { api, type LeagueWarmupStatus } from "@/lib/api";

const STEPS: { key: keyof LeagueWarmupStatus["stages"]; label: string }[] = [
  { key: "roster", label: "Reading your roster" },
  { key: "values", label: "Valuing your players" },
  { key: "trades", label: "Building trade ideas" },
];

const POLL_MS = 800;
// Past this the Dashboard simply loads what is left itself; never trap the user here.
const MAX_POLLS = 40;

/**
 * Shown right after a new league is saved. Each step reflects the server's
 * real warm-up progress (GET .../warmup-status); there are no timers or
 * percentages. A warm league (state "none"), a finished one, a failure or a
 * long wait all hand off to the Dashboard via onDone.
 */
export function LeagueWarmupProgress({ leagueId, onDone }: { leagueId: string; onDone: () => void }) {
  const [status, setStatus] = useState<LeagueWarmupStatus | null>(null);
  const doneRef = useRef(onDone);
  useEffect(() => {
    doneRef.current = onDone;
  }, [onDone]);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let polls = 0;

    const poll = async () => {
      polls += 1;
      try {
        const next = await api.getLeagueWarmupStatus(leagueId);
        if (cancelled) return;
        setStatus(next);
        if (next.state !== "running" || polls >= MAX_POLLS) {
          doneRef.current();
          return;
        }
      } catch {
        if (!cancelled) doneRef.current();
        return;
      }
      timer = setTimeout(poll, POLL_MS);
    };
    void poll();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [leagueId]);

  return (
    <div className="flex flex-col gap-3" role="status" aria-live="polite" data-testid="league-warmup-progress">
      <h2 style={{ font: "var(--font-card-title)" }}>Setting up your league</h2>
      <ul className="flex flex-col gap-2">
        {STEPS.map((step) => {
          const done = Boolean(status?.stages[step.key]);
          return (
            <li key={step.key} className="flex items-center gap-2 text-sm" data-done={done ? "true" : "false"}>
              <span
                aria-hidden="true"
                style={{ width: 16, color: done ? "var(--color-success, currentColor)" : "var(--color-text-muted)" }}
              >
                {done ? "✓" : "•"}
              </span>
              <span style={{ color: done ? "var(--color-text-primary)" : "var(--color-text-secondary)" }}>{step.label}</span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
