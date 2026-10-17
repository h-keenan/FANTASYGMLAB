"use client";

import { useState } from "react";

/**
 * Team/user profile picture — sibling to PlayerAvatar.tsx, same fallback
 * pattern (blank ringed circle on load failure or missing URL rather than a
 * broken-image icon). coridian_: "need team pfp" / "need team and user
 * pfps" (2026-10-17). Unlike PlayerAvatar, there's no fixed CDN base path —
 * every league-scoped API type that names a team (MatchupSide, HistorySide,
 * StorylineTeam, Trade Hub/Finder's partner_team_avatar_url, League
 * Rankings) already carries its own `avatar_url` field; this component just
 * renders whatever URL it's given.
 */
export function TeamAvatar({
  avatarUrl,
  size = 32,
  ringColor = "var(--color-border)",
}: {
  avatarUrl?: string | null;
  size?: number;
  ringColor?: string;
}) {
  const [failed, setFailed] = useState(false);
  const dimension = { width: size, height: size, borderRadius: "50%" };

  if (!avatarUrl || failed) {
    return (
      <span
        className="shrink-0"
        style={{ ...dimension, display: "inline-block", border: `2px solid ${ringColor}`, background: "var(--color-surface-muted)" }}
        aria-hidden
      />
    );
  }

  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={avatarUrl}
      alt=""
      style={{ ...dimension, border: `2px solid ${ringColor}`, objectFit: "cover" }}
      className="shrink-0"
      onError={() => setFailed(true)}
    />
  );
}
