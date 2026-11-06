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
  const [open, setOpen] = useState(false);
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
  // Collapsed by default behind a small "?" so beginner copy never pushes the
  // page's real content down; one tap reveals it, "Got it" hides it for good.
  return (
    <div data-beginner-help="true" className={`flex flex-wrap items-start gap-x-2 text-xs ${open ? "w-full" : ""} ${className}`.trim()} style={{ color: "var(--color-text-muted)" }}>
      <button
        type="button"
        aria-label={open ? "Hide explanation" : "What does this mean?"}
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className="inline-flex items-center justify-center font-bold shrink-0"
        style={{
          width: 20,
          height: 20,
          borderRadius: 9999,
          border: "var(--border-width-default) solid var(--color-border)",
          color: "var(--color-accent)",
          lineHeight: 1,
        }}
      >
        ?
      </button>
      {open ? (
        <p className="flex-1 min-w-0">
          {resolved}{" "}
          <button type="button" onClick={dismiss} className="font-bold underline" style={{ color: "var(--color-accent)" }}>
            Got it
          </button>
        </p>
      ) : null}
    </div>
  );
}
