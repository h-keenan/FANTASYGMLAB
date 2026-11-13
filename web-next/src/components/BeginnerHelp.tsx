"use client";

import { useState, useSyncExternalStore } from "react";

import { useExperienceCopy } from "@/context/ExperienceLevelContext";
import type { BeginnerHelpKey } from "@/lib/experienceCopy";

/**
 * Plain-language helper line for a beginner (onboarding experience level).
 * Renders nothing for advanced or unset accounts, so pages can drop it in
 * next to a term without their own conditional. Pass `term` for a fixed
 * entry from lib/experienceCopy.ts's BEGINNER_HELP, `text` for a value
 * already resolved through the same copy helpers (e.g. copy.verdictHelp()),
 * or `lines` for several terms behind one "?" (one chip instead of a row of
 * orphan circles).
 *
 * `popover` is for the SectionHeading `action` slot: the "?" sits on the
 * heading row and the explanation opens as a floating panel under it, so the
 * help never takes a row of its own.
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
  lines,
  popover = false,
  label,
  className = "",
}: {
  term?: BeginnerHelpKey;
  text?: string | null;
  lines?: Array<string | null | undefined>;
  popover?: boolean;
  /** REQUIRED name of what the "?" explains ("live scoring", "Value, Overall and Tier"). It is the button's accessible name ("About <label>"), and in inline mode it is also shown as visible text so the "?" is never an orphan circle. In `popover` mode place the component directly after the title it names (SectionHeading's `help` slot), never at a row's far edge. */
  label: string;
  className?: string;
}) {
  const copy = useExperienceCopy();
  const single = text !== undefined ? (copy.showsHelp ? text : null) : term ? copy.help(term) : null;
  const resolvedLines = lines ? (copy.showsHelp ? lines.filter((l): l is string => Boolean(l)) : []) : single ? [single] : [];
  const [dismissed, setDismissed] = useState(false);
  const [open, setOpen] = useState(false);
  const seen = useSyncExternalStore(
    noopSubscribe,
    () => resolvedLines.length > 0 && resolvedLines.every(readSeen),
    () => false,
  );
  if (resolvedLines.length === 0 || dismissed || seen) return null;
  function dismiss() {
    for (const line of resolvedLines) {
      try {
        window.localStorage.setItem(SEEN_PREFIX + line, "1");
      } catch {
        // storage blocked: just hide for this view
      }
    }
    setDismissed(true);
  }
  const body = (
    <>
      {popover ? (
        <button type="button" aria-label="Close explanation" onClick={() => setOpen(false)} className="float-right ml-2 font-bold" style={{ color: "var(--color-text-muted)" }}>
          ×
        </button>
      ) : null}
      {resolvedLines.map((line, index) => (
        <p key={line} className={index > 0 ? "mt-1" : undefined}>
          {line}
          {index === resolvedLines.length - 1 ? (
            <>
              {" "}
              <button type="button" onClick={dismiss} className="font-bold underline" style={{ color: "var(--color-accent)" }}>
                Got it
              </button>
            </>
          ) : null}
        </p>
      ))}
    </>
  );
  // Collapsed by default behind a small "?" so beginner copy never pushes the
  // page's real content down; one tap reveals it, "Got it" hides it for good.
  return (
    <div
      data-beginner-help="true"
      className={`${popover ? "relative inline-flex" : `flex flex-wrap items-start gap-x-2 ${open ? "w-full" : ""}`} text-xs ${className}`.trim()}
      style={{ color: "var(--color-text-muted)" }}
    >
      <button
        type="button"
        aria-label={open ? `Hide explanation of ${label}` : `About ${label}`}
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className="inline-flex items-center justify-center shrink-0"
        // 44px hit area around the 20px glyph without growing the layout.
        style={{ padding: 12, margin: -12 }}
      >
        <span
          aria-hidden="true"
          className="inline-flex items-center justify-center font-bold"
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
        </span>
      </button>
      {!open && !popover ? (
        <button type="button" tabIndex={-1} aria-hidden="true" onClick={() => setOpen(true)} className="font-semibold" style={{ color: "var(--color-text-muted)" }}>
          {label}
        </button>
      ) : null}
      {open ? (
        popover ? (
          <div role="dialog" aria-label={label} className="glass-surface z-20 p-3 max-sm:fixed max-sm:inset-x-3 max-sm:bottom-3 max-sm:w-auto sm:absolute sm:left-0 sm:top-full sm:mt-2 sm:w-72 sm:max-w-[calc(100vw-2rem)]" style={{ color: "var(--color-text-secondary)" }}>
            {body}
          </div>
        ) : (
          <div className="flex-1 min-w-0">{body}</div>
        )
      ) : null}
    </div>
  );
}
