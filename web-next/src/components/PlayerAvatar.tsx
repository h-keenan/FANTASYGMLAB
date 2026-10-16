"use client";

import { useState } from "react";

import { resolvePlayerTier } from "@/lib/playerTier";

const SLEEPER_HEADSHOT_BASE = "https://sleepercdn.com/content/nfl/players";

/**
 * Player headshot with a tier-colored "prestige" ring — ports mobile's
 * PlayerAvatar.tsx (same public Sleeper headshot CDN, same tier-ring
 * treatment via resolvePlayerTier). coridian_: "we need player images with
 * their prestige around in a ring" (2026-10-16) — this app's player rows
 * had no photo at all before this, only the canonical OvrGauge number
 * (which stays; this is an addition alongside it, not a replacement — see
 * OvrGauge's own "ALWAYS a circular gauge sitewide" docstring).
 *
 * Many players (rookies, IDP, deep bench) have no photo on Sleeper's CDN;
 * a load failure quietly falls back to a blank ringed circle rather than a
 * broken-image icon, same as mobile.
 */
export function PlayerAvatar({
  playerId,
  tier,
  size = 32,
}: {
  playerId: string | null | undefined;
  tier?: string | null;
  size?: number;
}) {
  const [failed, setFailed] = useState(false);
  const ringColor = `var(${resolvePlayerTier(tier).colorVar})`;
  const dimension = { width: size, height: size, borderRadius: "50%" };

  if (!playerId || failed) {
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
      src={`${SLEEPER_HEADSHOT_BASE}/${playerId}.jpg`}
      alt=""
      style={{ ...dimension, border: `2px solid ${ringColor}`, objectFit: "cover", objectPosition: "top" }}
      className="shrink-0"
      onError={() => setFailed(true)}
    />
  );
}
