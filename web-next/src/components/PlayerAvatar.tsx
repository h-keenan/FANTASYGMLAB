"use client";

import { useState, type CSSProperties } from "react";

import { resolvePlayerTier, tierGlowIntensity, type TierGlowIntensity } from "@/lib/playerTier";

// Same escape hatch as OvrGauge.tsx's GaugeStyle — CSS custom properties
// aren't part of React's CSSProperties typing.
type GlowStyle = CSSProperties & {
  "--glow-color"?: string;
  "--glow-min"?: string;
  "--glow-max"?: string;
  "--glow-duration"?: string;
};

// coridian_, 2026-10-19 (queued cosmetic, lowest priority): "an effect
// around the prestige ring ... kind of a glowing effect, kind of a fire
// effect ... different for different tiers. Obviously lower tiers don't
// need one." Values feed the CSS custom properties .prestige-glow reads
// (globals.css) — bigger/brighter/faster for a higher tier.
const GLOW_STYLE_BY_INTENSITY: Record<Exclude<TierGlowIntensity, null>, { min: string; max: string; duration: string }> = {
  strong: { min: "5px", max: "16px", duration: "1.8s" },
  medium: { min: "3px", max: "11px", duration: "2.3s" },
  subtle: { min: "2px", max: "7px", duration: "2.8s" },
};

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
  // Same gate as `title`: only a caller-supplied tier can glow, never the
  // untiered DEFAULT_TIER fallback resolvePlayerTier returns for a row with
  // no tier concept at all (e.g. League Recaps).
  const glowIntensity = tier ? tierGlowIntensity(tierIdentity.tierId) : null;
  const glowStyle: GlowStyle | undefined = glowIntensity
    ? {
        "--glow-color": ringColor,
        "--glow-min": GLOW_STYLE_BY_INTENSITY[glowIntensity].min,
        "--glow-max": GLOW_STYLE_BY_INTENSITY[glowIntensity].max,
        "--glow-duration": GLOW_STYLE_BY_INTENSITY[glowIntensity].duration,
      }
    : undefined;
  const glowClassName = glowIntensity ? " prestige-glow" : "";

  if (!playerId || failed) {
    return (
      <span
        className={`shrink-0${glowClassName}`}
        style={{
          ...dimension,
          ...glowStyle,
          display: "inline-block",
          border: `${borderWidth}px solid ${ringColor}`,
          background: "var(--color-surface-muted)",
        }}
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
      style={{ ...dimension, ...glowStyle, border: `${borderWidth}px solid ${ringColor}`, objectFit: "cover", objectPosition: "top" }}
      className={`shrink-0${glowClassName}`}
      onError={() => setFailed(true)}
    />
  );
}
