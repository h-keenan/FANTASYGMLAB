"use client";

import Link from "next/link";
import { useCallback, useMemo, useSyncExternalStore } from "react";

import { AccentCard } from "@/components/AccentCard";
import { SectionHeading } from "@/components/SectionHeading";
import {
  EMPTY_START_HERE_STATE,
  START_HERE_STEPS,
  START_HERE_SUBTITLE,
  START_HERE_TITLE,
  markStartHereStepDone,
  parseStartHereState,
  shouldShowStartHere,
  startHereStorageKey,
  type StartHereRoute,
  type StartHereState,
} from "@/lib/startHere";
import { thisWeekHref } from "@/lib/thisWeek";

const startHereListeners = new Set<() => void>();
// Only populated when a localStorage write fails, so the card still reflects
// the change for this page view.
const startHereUnsaved = new Map<string, string>();

function subscribeStartHere(onChange: () => void) {
  startHereListeners.add(onChange);
  window.addEventListener("storage", onChange);
  return () => {
    startHereListeners.delete(onChange);
    window.removeEventListener("storage", onChange);
  };
}

function readRaw(userId: string): string | null {
  const key = startHereStorageKey(userId);
  const unsaved = startHereUnsaved.get(key);
  if (unsaved !== undefined) return unsaved;
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

function writeState(userId: string, state: StartHereState) {
  const key = startHereStorageKey(userId);
  const raw = JSON.stringify(state);
  try {
    window.localStorage.setItem(key, raw);
    startHereUnsaved.delete(key);
  } catch {
    // Best-effort: worst case the card shows again.
    startHereUnsaved.set(key, raw);
  }
  startHereListeners.forEach((listener) => listener());
}

/**
 * First-run checklist for a newly created account: three destinations, each
 * ticked when opened, dismissible. Per-device state (localStorage, try/catch),
 * only for accounts under START_HERE_WINDOW_DAYS old. Mobile twin:
 * mobile/src/components/StartHereCard.tsx.
 */
export function StartHereCard({
  userId,
  accountCreatedAt,
  leagueId,
  leagueName,
}: {
  userId: string;
  accountCreatedAt: string | null | undefined;
  leagueId: string;
  leagueName: string;
}) {
  // null until read on the client, so server and first client render match.
  const getSnapshot = useCallback(() => readRaw(userId), [userId]);
  const raw = useSyncExternalStore(subscribeStartHere, getSnapshot, () => undefined);
  const state = useMemo<StartHereState | null>(
    () => (raw === undefined ? null : parseStartHereState(raw)),
    [raw],
  );

  if (!state || !shouldShowStartHere(state, accountCreatedAt)) return null;

  const update = (next: StartHereState) => {
    writeState(userId, next);
  };

  return (
    <section className="flex flex-col gap-2" aria-labelledby="start-here-heading" data-testid="start-here">
      <SectionHeading
        id="start-here-heading"
        action={
          <button
            type="button"
            onClick={() => update({ ...state, dismissed: true })}
            className="text-sm font-bold inline-flex items-center min-h-[var(--touch-target-min)]"
            style={{ color: "var(--color-text-secondary)" }}
          >
            Hide
          </button>
        }
      >
        {START_HERE_TITLE}
      </SectionHeading>
      <AccentCard accent="var(--color-accent)" compact>
        <p className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
          {START_HERE_SUBTITLE}
        </p>
        <ul className="flex flex-col" style={{ listStyle: "none", margin: 0, padding: 0 }}>
          {START_HERE_STEPS.map((step, index) => {
            const done = state.done.includes(step.key);
            return (
              <li key={step.key} style={index > 0 ? { borderTop: "1px solid var(--color-border)" } : undefined}>
                <Link
                  href={thisWeekHref(step.key as StartHereRoute, leagueId, leagueName)}
                  onClick={() => update(markStartHereStepDone(state, step.key))}
                  className="flex items-center gap-3 py-2 min-h-[var(--touch-target-min)]"
                >
                  <span
                    aria-hidden="true"
                    className="shrink-0 font-bold"
                    style={{ width: 20, color: done ? "var(--color-success)" : "var(--color-text-muted)" }}
                  >
                    {done ? "✓" : "○"}
                  </span>
                  <span className="min-w-0 flex-1 flex flex-col">
                    <span className="text-sm font-bold">
                      {step.label}
                      <span className="sr-only">{done ? " (done)" : ""}</span>
                    </span>
                    <span className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
                      {step.why}
                    </span>
                  </span>
                  <span aria-hidden="true" style={{ color: "var(--color-accent)" }}>
                    →
                  </span>
                </Link>
              </li>
            );
          })}
        </ul>
      </AccentCard>
    </section>
  );
}
