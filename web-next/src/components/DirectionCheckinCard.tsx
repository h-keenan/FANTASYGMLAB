"use client";

import { useEffect, useReducer } from "react";

import { AccentCard } from "@/components/AccentCard";
import { Button } from "@/components/Button";
import { api, type TeamStance } from "@/lib/api";
import {
  DIRECTION_CHECKIN_INITIAL,
  directionChangedMessage,
  directionCheckinReducer,
  directionSwitchLabel,
  type DirectionCheckinAction,
  type DirectionCheckinOption,
} from "@/lib/directionCheckin";

/**
 * Dashboard direction check-in. A few times a season (start of season,
 * midseason, trade deadline, playoff push) the server says whether to ask if
 * the declared Team Situation still fits, and writes the words (see
 * lib/directionCheckin.ts and modules/direction_checkin.py). Answering goes
 * through the normal Team Situation write; every answer, a dismissal included,
 * ends that moment for the season, so there is no nag loop. Self-fetching and
 * silent on any failure: a Dashboard extra must never block or break the page.
 */
export function DirectionCheckinCard({ leagueId, onChanged }: { leagueId: string; onChanged?: () => void }) {
  const [state, dispatch] = useReducer(directionCheckinReducer, DIRECTION_CHECKIN_INITIAL);

  useEffect(() => {
    let cancelled = false;
    api
      .getDirectionCheckin(leagueId)
      .then((response) => {
        if (!cancelled) dispatch({ type: "loaded", response });
      })
      .catch(() => {
        if (!cancelled) dispatch({ type: "loaded", response: null });
      });
    return () => {
      cancelled = true;
    };
  }, [leagueId]);

  if (state.phase === "changed") {
    return (
      <AccentCard accent="var(--color-accent)" compact as="section" data-testid="direction-checkin-done">
        <p className="m-0 text-sm" role="status">{directionChangedMessage(state.label)}</p>
      </AccentCard>
    );
  }
  if (state.phase !== "ready" && state.phase !== "saving") return null;
  const { prompt } = state;
  const saving = state.phase === "saving";
  const error = state.phase === "ready" ? state.error : "";

  async function record(action: DirectionCheckinAction) {
    try {
      await api.answerDirectionCheckin(leagueId, prompt.momentKey, action);
    } catch {
      // Only used to avoid asking again; the answer itself already took effect.
    }
  }

  async function answer(action: "kept" | "dismissed") {
    dispatch({ type: "save" });
    await record(action);
    dispatch({ type: "answered", action });
  }

  async function change(option: DirectionCheckinOption) {
    dispatch({ type: "save" });
    try {
      await api.setTeamStance(leagueId, option.value as TeamStance);
    } catch {
      dispatch({ type: "failed" });
      return;
    }
    await record("changed");
    dispatch({ type: "answered", action: "changed", label: option.label });
    onChanged?.();
  }

  return (
    <AccentCard accent="var(--color-accent)" as="section" data-testid="direction-checkin" aria-label="Direction check-in">
      <div className="flex items-start justify-between gap-2">
        <div className="flex flex-col gap-1">
          <h2 className="m-0" style={{ font: "var(--font-card-title)" }}>{prompt.headline}</h2>
          <p className="m-0 text-sm" style={{ color: "var(--color-text-secondary)" }}>{prompt.body}</p>
        </div>
        <button
          type="button"
          aria-label="Dismiss direction check-in"
          disabled={saving}
          onClick={() => void answer("dismissed")}
          className="tap-link justify-center shrink-0 text-sm"
          style={{ minWidth: "var(--touch-target-min)", color: "var(--color-text-muted)" }}
        >
          ✕
        </button>
      </div>
      <div className="flex flex-wrap gap-2">
        <Button size="sm" loading={saving} disabled={saving} onClick={() => void answer("kept")}>{prompt.keepLabel}</Button>
        {prompt.options.map((option) => (
          <Button key={option.value} size="sm" variant="secondary" disabled={saving} onClick={() => void change(option)}>
            {directionSwitchLabel(option)}
          </Button>
        ))}
        <Button size="sm" variant="ghost" disabled={saving} onClick={() => void answer("dismissed")}>{prompt.dismissLabel}</Button>
      </div>
      {error ? <p className="m-0 text-xs" role="alert" style={{ color: "var(--color-danger)" }}>{error}</p> : null}
    </AccentCard>
  );
}
