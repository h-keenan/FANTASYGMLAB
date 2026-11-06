"use client";

import { useState, useSyncExternalStore } from "react";

import { useExperienceCopy } from "@/context/ExperienceLevelContext";
import type { BeginnerHelpKey } from "@/lib/experienceCopy";

/**
 * Plain-language helper line for a beginner (onboarding experience level).
 * Renders nothing for advanced or unset accounts, so pages can drop it in
 * next to a term without their own conditional. Pass `term` for a fixed
 * entry from lib/experienceCopy.ts's BEGINNER_HELP, or `text` for a value
 * already resolved through the same copy helpers (e.g. copy.verdictHelp()).
 */
const SEEN_PREFIX = "fd-help-seen:";

function readSeen(key: string): boolean {
  try {
    return window.localStorage.getItem(SEEN_PREFIX + key) === "1";
  } catch {
    return false;
  }
}

const noopSubscribe = () => () => {};

/** Shown once: a "Got it" tap hides this exact line for good (per browser). */
export function BeginnerHelp({
  term,
  text,
  className = "",
}: {
  term?: BeginnerHelpKey;
  text?: string | null;
  className?: string;
}) {
  const copy = useExperienceCopy();
  const resolved = text !== undefined ? (copy.isBeginner ? text : null) : term ? copy.help(term) : null;
  const [dismissed, setDismissed] = useState(false);
  const seen = useSyncExternalStore(
    noopSubscribe,
    () => (resolved ? readSeen(resolved) : false),
    () => false,
  );
  if (!resolved || dismissed || seen) return null;
  function dismiss() {
    try {
      window.localStorage.setItem(SEEN_PREFIX + resolved, "1");
    } catch {
      // storage blocked: just hide for this view
    }
    setDismissed(true);
  }
  return (
    <p data-beginner-help="true" className={`text-xs ${className}`.trim()} style={{ color: "var(--color-text-muted)" }}>
      {resolved}{" "}
      <button type="button" onClick={dismiss} className="font-bold underline" style={{ color: "var(--color-accent)" }}>
        Got it
      </button>
    </p>
  );
}
