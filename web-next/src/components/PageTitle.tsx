"use client";

import { useSyncExternalStore, type ReactNode } from "react";
import { createPortal } from "react-dom";

import { InfoMark } from "@/components/ui/InfoMark";

const noopSubscribe = () => () => {};

/** DOM id of the slot Header.tsx renders next to the page name. */
export const PAGE_INFO_SLOT_ID = "page-info-slot";
/** Same slot in the phone shell header (ShellHeader.tsx); the visible one wins. */
export const SHELL_PAGE_INFO_SLOT_ID = "shell-page-info-slot";

function visibleInfoSlot(): HTMLElement | null {
  const slots = [SHELL_PAGE_INFO_SLOT_ID, PAGE_INFO_SLOT_ID].map((id) => document.getElementById(id));
  return slots.find((el) => el && el.getClientRects().length > 0) ?? slots.find(Boolean) ?? null;
}

/**
 * The one page heading for league pages. The persistent top bar
 * (Header.tsx HeaderPageTitle) already shows the page name and the league
 * picker already shows the league, so repeating a big visible title pushed
 * the real content down the phone viewport (coridian_, 2026-11-06). The
 * <h1> stays in the DOM, visually hidden, so screen readers and the document
 * outline still hear the page name.
 *
 * `info` is the page's one explanatory sentence (e.g. Trade Hub's posture
 * line). It renders as the shared InfoMark "?" next to the page name in the header row
 * instead of as its own row of page content. Without the header slot (tests,
 * signed-out pages) it falls back to inline.
 */
export function PageTitle({ page, info }: { page: string; leagueName?: string; info?: ReactNode }) {
  // The header slot only exists in the browser, after the shell mounts: read it
  // as an external value (null on the server) instead of syncing it via an effect.
  const slot = useSyncExternalStore(
    noopSubscribe,
    visibleInfoSlot,
    () => null,
  );
  const button = info ? <InfoMark label={page}>{info}</InfoMark> : null;
  return (
    <>
      <h1 className="sr-only">{page}</h1>
      {button ? (slot ? createPortal(button, slot) : <div className="relative">{button}</div>) : null}
    </>
  );
}
