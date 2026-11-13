"use client";

import { useState, useSyncExternalStore, type ReactNode } from "react";
import { createPortal } from "react-dom";

const noopSubscribe = () => () => {};

/** DOM id of the slot Header.tsx renders next to the page name. */
export const PAGE_INFO_SLOT_ID = "page-info-slot";

/**
 * The one page heading for league pages. The persistent top bar
 * (Header.tsx HeaderPageTitle) already shows the page name and the league
 * picker already shows the league, so repeating a big visible title pushed
 * the real content down the phone viewport (coridian_, 2026-11-06). The
 * <h1> stays in the DOM, visually hidden, so screen readers and the document
 * outline still hear the page name.
 *
 * `info` is the page's one explanatory sentence (e.g. Trade Hub's posture
 * line). It renders behind a "?" next to the page name in the header row
 * instead of as its own row of page content. Without the header slot (tests,
 * signed-out pages) it falls back to inline.
 */
export function PageTitle({ page, info }: { page: string; leagueName?: string; info?: ReactNode }) {
  // The header slot only exists in the browser, after the shell mounts: read it
  // as an external value (null on the server) instead of syncing it via an effect.
  const slot = useSyncExternalStore(
    noopSubscribe,
    () => document.getElementById(PAGE_INFO_SLOT_ID),
    () => null,
  );
  const [open, setOpen] = useState(false);
  const button = info ? (
    <>
      <button
        type="button"
        aria-label={open ? `Hide explanation of ${page}` : `About ${page}`}
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className="inline-flex items-center justify-center -mx-2"
        style={{ width: "var(--touch-target-min)", height: "var(--touch-target-min)" }}
      >
        <span
          className="inline-flex items-center justify-center text-xs font-bold"
          style={{ width: 20, height: 20, borderRadius: 9999, border: "var(--border-width-default) solid var(--color-border)", color: "var(--color-accent)", lineHeight: 1 }}
        >
          ?
        </span>
      </button>
      {open ? (
        <div role="note" className="glass-surface absolute left-4 right-4 top-full mt-1 p-3 text-xs" style={{ zIndex: 50, color: "var(--color-text-secondary)" }}>
          {info}
        </div>
      ) : null}
    </>
  ) : null;
  return (
    <>
      <h1 className="sr-only">{page}</h1>
      {button ? (slot ? createPortal(button, slot) : <div className="relative">{button}</div>) : null}
    </>
  );
}
