"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

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

function readState(userId: string): StartHereState {
  try {
    return parseStartHereState(window.localStorage.getItem(startHereStorageKey(userId)));
  } catch {
    return EMPTY_START_HERE_STATE;
  }
}

function writeState(userId: string, state: StartHereState) {
  try {
    window.localStorage.setItem(startHereStorageKey(userId), JSON.stringify(state));
  } catch {
    // Best-effort: worst case the card shows again.
  }
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
  const [state, setState] = useState<StartHereState | null>(null);
  useEffect(() => {
    setState(readState(userId));
  }, [userId]);

  if (!state || !shouldShowStartHere(state, accountCreatedAt)) return null;

  const update = (next: StartHereState) => {
    setState(next);
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
