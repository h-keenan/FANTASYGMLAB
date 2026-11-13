"use client";

import { useId, useState, useSyncExternalStore, type ReactNode } from "react";

import { AccentCard } from "@/components/AccentCard";
import { simOpenKey, simParseOpen } from "@/lib/simLayout";

const OPEN_EVENT = "fgl:sim-open-change";

function readStored(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

/**
 * The one collapsible card. A header button (aria-expanded / aria-controls)
 * that toggles the body; the open state is remembered per `id` in
 * localStorage so a section the player closed stays closed next visit. Used by
 * every dense screen of the Fantasy Sim game so phone layouts are
 * summary-first. No animation, so reduced-motion needs no special casing.
 * Mobile twin: mobile/src/components/Collapsible.tsx.
 */
export function Collapsible({
  id,
  title,
  summary,
  accent = "var(--color-accent)",
  defaultOpen = true,
  children,
  testId,
}: {
  /** Stable key for remembering the open state, e.g. "home.injuries". */
  id: string;
  title: ReactNode;
  /** Right-aligned, always visible (a count badge or one-line status). */
  summary?: ReactNode;
  accent?: string;
  defaultOpen?: boolean;
  children: ReactNode;
  testId?: string;
}) {
  const key = simOpenKey(id);
  const bodyId = useId();
  // The remembered flag lives in localStorage; the server snapshot is null so the first client frame
  // matches the server. `override` covers storage that is blocked (private mode): the toggle still works.
  const stored = useSyncExternalStore(
    (notify) => {
      window.addEventListener("storage", notify);
      window.addEventListener(OPEN_EVENT, notify);
      return () => {
        window.removeEventListener("storage", notify);
        window.removeEventListener(OPEN_EVENT, notify);
      };
    },
    () => readStored(key),
    () => null,
  );
  const [override, setOverride] = useState<boolean | null>(null);
  const open = override ?? simParseOpen(stored, defaultOpen);

  function toggle() {
    const next = !open;
    setOverride(next);
    try {
      window.localStorage.setItem(key, next ? "1" : "0");
      window.dispatchEvent(new Event(OPEN_EVENT));
    } catch {
      /* storage blocked: the override keeps this session consistent */
    }
  }

  return (
    <AccentCard accent={accent} as="section" compact className="min-w-0" data-testid={testId}>
      <button
        type="button"
        aria-expanded={open}
        aria-controls={bodyId}
        onClick={toggle}
        className="flex w-full items-center gap-2 text-left"
        style={{ minHeight: "var(--touch-target-min)" }}
      >
        <span className="min-w-0 flex-1 text-sm font-extrabold uppercase" style={{ letterSpacing: "0.02em" }}>{title}</span>
        {summary ? <span className="shrink-0">{summary}</span> : null}
        <span aria-hidden="true" className="shrink-0 text-xs" style={{ color: "var(--color-text-muted)", width: 12, textAlign: "center" }}>
          {open ? "−" : "+"}
        </span>
      </button>
      <div id={bodyId} hidden={!open} className="flex flex-col gap-3 pt-1">
        {open ? children : null}
      </div>
    </AccentCard>
  );
}
