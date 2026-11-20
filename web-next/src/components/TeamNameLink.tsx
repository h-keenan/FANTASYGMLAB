"use client";

import dynamic from "next/dynamic";
import { useState, type ReactNode } from "react";

import { TeamAvatar } from "@/components/TeamAvatar";
import { teamDisplayName, teamLinkInteractive, teamOpenLabel, TEAM_TAP_MIN } from "@/lib/teamTap";

const ManagerProfileSheet = dynamic(() => import("@/components/ManagerProfileSheet").then((m) => m.ManagerProfileSheet), { ssr: false });

/**
 * THE team tap target (twin of mobile TeamNameLink.tsx; rule in lib/teamTap.ts): a league team's name, optionally with its
 * avatar, opens the shared team sheet (ManagerProfileSheet, the same one the trade card's "View ... team sheet" button
 * opens). One real button with a label and a 44px minimum height. Renders plain (no button) when the league or roster is
 * unknown, or when `current` says the screen is already that team's own page (a tap would be a no-op).
 */
export function TeamNameLink({
  leagueId,
  leagueName,
  rosterId,
  name,
  avatarUrl,
  showAvatar = false,
  avatarSize = 24,
  current = false,
  className = "",
  children,
}: {
  leagueId?: string | null;
  leagueName?: string;
  rosterId?: string | number | null;
  name?: string | null;
  avatarUrl?: string | null;
  /** Draw the team avatar inside the same tap target, before the name. */
  showAvatar?: boolean;
  avatarSize?: number;
  /** The screen is already this team's own page: render plain. */
  current?: boolean;
  className?: string;
  /** Replaces the default name text (the tap target stays the same). */
  children?: ReactNode;
}) {
  const [sheetOpen, setSheetOpen] = useState(false);
  const shown = teamDisplayName(name);
  const content = (
    <>
      {showAvatar ? <TeamAvatar avatarUrl={avatarUrl} name={name} size={avatarSize} /> : null}
      <span className="min-w-0 break-words">{children ?? shown}</span>
    </>
  );
  if (!teamLinkInteractive({ leagueId, rosterId, name }, current) || !leagueId || rosterId == null) {
    return <span className={`inline-flex items-center gap-2 min-w-0 ${className}`}>{content}</span>;
  }
  return (
    <>
      <button
        type="button"
        data-testid="team-name-link"
        aria-label={teamOpenLabel(name)}
        aria-haspopup="dialog"
        onClick={() => setSheetOpen(true)}
        className={`inline-flex items-center gap-2 min-w-0 text-left underline decoration-dotted underline-offset-2 ${className}`}
        style={{ minHeight: TEAM_TAP_MIN, color: "inherit", font: "inherit" }}
      >
        {content}
      </button>
      {sheetOpen ? (
        <ManagerProfileSheet
          leagueId={leagueId}
          leagueName={leagueName}
          rosterId={rosterId}
          teamName={shown}
          avatarUrl={avatarUrl}
          onClose={() => setSheetOpen(false)}
        />
      ) : null}
    </>
  );
}
