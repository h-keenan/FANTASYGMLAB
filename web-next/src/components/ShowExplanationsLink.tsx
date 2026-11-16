"use client";

import { useState } from "react";

import { useExperienceLevel } from "@/context/ExperienceLevelContext";
import { PLAIN_COPY } from "@/lib/experienceCopy";

/**
 * "Show explanations": the in-context way back for someone who chose Veteran (or never answered) and then hits a
 * term they want explained. It writes the same preference as Account > Explanations (`setLevel("beginner")`, the
 * "explain the why" level), so nothing here is a second source of truth. Renders nothing once the level is already
 * a beginner one. Twin: mobile/src/components/ShowExplanationsLink.tsx.
 */
export function ShowExplanationsLink({ className = "" }: { className?: string }) {
  const { level, setLevel } = useExperienceLevel();
  const [done, setDone] = useState(false);
  const [error, setError] = useState(false);
  if (done) {
    return (
      <span className={`text-xs ${className}`.trim()} style={{ color: "var(--color-text-muted)" }} role="status">
        {PLAIN_COPY.showExplanationsDone}
      </span>
    );
  }
  if (level === "beginner" || level === "new_to_fantasy") return null;
  return (
    <button
      type="button"
      data-testid="show-explanations"
      className={`inline-flex items-center font-bold underline ${className}`.trim()}
      style={{ color: "var(--color-accent)", minHeight: "var(--touch-target-min)" }}
      onClick={() => {
        setError(false);
        setLevel("beginner").then(
          () => setDone(true),
          () => setError(true),
        );
      }}
    >
      {error ? "Couldn't save. Try again" : PLAIN_COPY.showExplanationsAction}
    </button>
  );
}
