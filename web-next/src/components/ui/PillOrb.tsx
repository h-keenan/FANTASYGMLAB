"use client";

import Image from "next/image";
import type { Ref } from "react";

import { bottomTabBadgeText } from "@/lib/bottomNav";

import "./ui.css";

/**
 * THE footer orb: the one navigation / menu control of every phone footer (the site shell pill and the Fantasy Sim bar).
 * Brand mark + a count badge, 48px round glass. There is no separate "..." or section button next to it: tapping the orb
 * opens the menu (the shell unfolds its section row and More, the Fantasy Sim opens its page menu with search, Sim to,
 * All games). Mobile twin: mobile/src/components/PillOrb.tsx.
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
}) {
  const text = bottomTabBadgeText(badge);
  return (
    <button
      ref={buttonRef}
      type="button"
      className="game-orb game-orb--bar"
      onClick={onClick}
      aria-label={label}
      aria-expanded={expanded}
      aria-haspopup={popup ? "dialog" : undefined}
      data-testid={testId}
      data-pill-orb=""
    >
      {/* Brand mark only: a page name in 9px caps is wider than the 48px circle and clips on its rim. The accessible name carries the page and the count. */}
      <Image src="/brand-mark.png" alt="" width={26} height={26} className="brand-mark-icon" style={{ objectFit: "contain" }} />
      {text ? (
        <span className="game-orb-badge" aria-hidden="true" data-testid={badgeTestId ?? `${testId}-badge`}>
          {text}
        </span>
      ) : null}
    </button>
  );
}
