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
  const tierIdentity = resolvePlayerTier(tier);
  const ringColor = `var(${tierIdentity.colorVar})`;
  const dimension = { width: size, height: size, borderRadius: "50%" };
  // coridian_, 2026-10-18: "The prestige ring is still too small around
  // player PFP's" — a flat 2px border read fine at the 24-32px sizes most
  // list rows use, but PQV's 112px hero avatar (bumped up from 88px
  // earlier today) made the same 2px ring proportionally even thinner.
  // Scales up only for the larger hero-sized avatars; small list rows stay
  // exactly as they were.
  const borderWidth = size >= 80 ? 5 : size >= 40 ? 3 : 2;
  // coridian_: the ring color's meaning is never explained anywhere — a
  // hover tooltip naming the tier is the cheapest fix that doesn't require
  // new on-page UI real estate. Only shown when a caller actually passed a
  // tier (some rows, e.g. League Recaps, render this avatar with no tier
  // concept at all, where resolvePlayerTier's "Depth / Developmental"
  // default would be a misleading tooltip, not a real classification).
  const title = tier ? tierIdentity.semanticLabel : undefined;

  if (!playerId || failed) {
    return (
      <span
        className="shrink-0"
        style={{ ...dimension, display: "inline-block", border: `${borderWidth}px solid ${ringColor}`, background: "var(--color-surface-muted)" }}
        title={title}
        aria-hidden
      />
    );
  }

  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={`${SLEEPER_HEADSHOT_BASE}/${playerId}.jpg`}
      alt=""
      title={title}
      style={{ ...dimension, border: `${borderWidth}px solid ${ringColor}`, objectFit: "cover", objectPosition: "top" }}
      className="shrink-0"
      onError={() => setFailed(true)}
    />
  );
}
