"use client";

import Image from "next/image";
import { useEffect, useState, type Ref } from "react";

import { bottomTabBadgeText } from "@/lib/bottomNav";
import { ORB_COACHMARK_SEEN_KEY, ORB_COACHMARK_TEXT } from "@/lib/orbCoachmark";

import "./ui.css";

const CUE_MENU_PATH = "M1.5 2.5h7M1.5 5h7M1.5 7.5h7";
const CUE_CLOSE_PATH = "M2 2l6 6M8 2L2 8";

/**
 * THE footer orb: the one navigation / menu control of every phone footer (the site shell pill and the Fantasy Sim bar).
 * Brand mark + a count badge, 48px round glass. There is no separate "..." or section button next to it: tapping the orb
 * opens the menu (the shell unfolds its section row and More, the Fantasy Sim opens its page menu with search, Sim to,
 * All games). Mobile twin: the app GmOrb (mobile/src/components/GmOrb.tsx).
 *
 * A logo is not a menu, so the orb carries a persistent "menu" cue (three bars on its rim, a close mark while the menu is
 * open) and, where `coachmark` is set, a one-time coachmark naming what it opens (first-time-user audit F1). The coachmark
 * is seen-once per browser (`fd-help-seen:` like BeginnerHelp) and goes away on the first orb tap or after a few seconds.
 */
export function PillOrb({
  label,
  badge = 0,
  onClick,
  expanded,
  popup,
  testId = "pill-orb",
  badgeTestId,
  buttonRef,
  coachmark = false,
}: {
  /** Accessible name (starts with what the orb shows, WCAG 2.5.3). */
  label: string;
  badge?: number;
  onClick: () => void;
  /** Shell pill: the section row is unfolded. */
  expanded?: boolean;
  /** Opens a dialog (the Fantasy Sim page menu). */
  popup?: boolean;
  testId?: string;
  badgeTestId?: string;
  buttonRef?: Ref<HTMLButtonElement>;
  /** First-run coachmark anchored on the orb (the global shell pill sets it; the Sim bar keeps its own cues). */
  coachmark?: boolean;
}) {
  const text = bottomTabBadgeText(badge);
  const [coachOpen, setCoachOpen] = useState(false);
  const dismissCoach = () => {
    setCoachOpen(false);
    try {
      window.localStorage.setItem(ORB_COACHMARK_SEEN_KEY, "1");
    } catch {
      // storage blocked: just hide for this view
    }
  };
  /* eslint-disable react-hooks/set-state-in-effect -- localStorage is client-only, read after mount */
  useEffect(() => {
    if (!coachmark) return;
    let seen = false;
    try {
      seen = window.localStorage.getItem(ORB_COACHMARK_SEEN_KEY) === "1";
    } catch {
      seen = false;
    }
    if (seen) return;
    setCoachOpen(true);
    const timer = window.setTimeout(() => {
      setCoachOpen(false);
      try {
        window.localStorage.setItem(ORB_COACHMARK_SEEN_KEY, "1");
      } catch {
        // storage blocked
      }
    }, 12000);
    return () => window.clearTimeout(timer);
  }, [coachmark]);
  /* eslint-enable react-hooks/set-state-in-effect */
  return (
    <button
      ref={buttonRef}
      type="button"
      className="game-orb game-orb--bar"
      onClick={() => {
        if (coachOpen) dismissCoach();
        onClick();
      }}
      aria-label={label}
      aria-expanded={expanded}
      aria-haspopup={popup ? "dialog" : undefined}
      data-testid={testId}
      data-pill-orb=""
    >
      {/* Brand mark only: a page name in 9px caps is wider than the 48px circle and clips on its rim. The accessible name carries the page and the count. */}
      <Image src="/brand-mark.png" alt="" width={26} height={26} className="brand-mark-icon" style={{ objectFit: "contain" }} />
      {/* Persistent menu cue: aria-hidden, the accessible name already says "Menu". */}
      <span className="game-orb-cue" aria-hidden="true" data-testid={`${testId}-cue`} data-open={expanded ? "true" : undefined}>
        <svg viewBox="0 0 10 10" width="8" height="8">
          <path d={expanded ? CUE_CLOSE_PATH : CUE_MENU_PATH} stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" fill="none" />
        </svg>
      </span>
      {coachOpen && !expanded ? (
        <span className="game-orb-coach glass-surface" role="status" data-testid={`${testId}-coachmark`}>
          {ORB_COACHMARK_TEXT}
        </span>
      ) : null}
      {text ? (
        <span className="game-orb-badge" aria-hidden="true" data-testid={badgeTestId ?? `${testId}-badge`}>
          {text}
        </span>
      ) : null}
    </button>
  );
}
