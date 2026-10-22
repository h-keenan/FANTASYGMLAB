/**
 * Shared share-card frame and primitives, drawn with next/og (Satori).
 * Every card kind (trade, player, the site preview) composes these, so the
 * header, glass panels, badges, rings and footer stay one definition, the
 * same "one shared primitive, the card supplies the content" rule mobile's
 * ShareCardChrome follows.
 *
 * Satori notes: every element with more than one child needs
 * display:flex; there is no backdrop-filter, so "glass" is the same
 * gradient, hairline rim and top highlight as globals.css's .glass-surface,
 * drawn without the blur.
 */

import type { CSSProperties, ReactNode } from "react";

import { BRAND_DOMAIN, BRAND_NAME } from "@/lib/brand";

import { SHARE_TOKEN_HEX as T, overallRatingTintHex, positionHex, shareRadius, tierHex, withAlpha } from "./tokens";

export const SHARE_FONT_FAMILY = "Inter";

/** Portrait 4:5, the size Instagram/X/iMessage show uncropped. */
export const STORY_SIZE = { width: 1080, height: 1350 } as const;
/** Open Graph / X large-summary preview. */
export const OG_SIZE = { width: 1200, height: 630 } as const;

export interface ShareBrandAssets {
  /** data: URI of the white FantasyDesk lockup (mark + wordmark). */
  lockup: string;
  /** data: URI of the canonical site QR (modules.share_card_qr's URL). */
  qr: string;
  /** data: URI of the pre-rendered ShareBackdrop for this card size. */
  backdrop?: string;
}

/** .glass-surface, in Satori terms. The inset top highlight is a brighter
 * top border rather than an inset box-shadow, and there is no drop shadow:
 * Satori rasterizes blurred shadows slowly (~0.7s per panel), and a shadow
 * on a black card is close to invisible anyway. */
export function glassStyle(radius = shareRadius("--radius-panel")): CSSProperties {
  return {
    display: "flex",
    backgroundImage: "linear-gradient(165deg, rgba(50, 54, 60, 0.72), rgba(24, 26, 30, 0.9))",
    border: "1.5px solid rgba(255, 255, 255, 0.14)",
    borderTop: "2px solid rgba(255, 255, 255, 0.26)",
    borderRadius: radius,
  };
}

/** The app's ambient cyan field (.app-background-field), as two soft glows.
 * Rendered once per card size into a PNG (server.tsx's backdrop cache) and
 * reused as an image, since radial gradients are slow to rasterize. */
export function ShareBackdrop({ width, height }: { width: number; height: number }) {
  return (
    <div
      style={{
        width,
        height,
        display: "flex",
        backgroundColor: T["--color-bg"],
        backgroundImage: [
          `radial-gradient(circle at 12% 0%, ${withAlpha(T["--color-accent-strong"], 0.22)}, rgba(0, 0, 0, 0) 52%)`,
          `radial-gradient(circle at 100% 100%, ${withAlpha(T["--color-accent"], 0.12)}, rgba(0, 0, 0, 0) 48%)`,
        ].join(", "),
      }}
    />
  );
}

/** Same uppercase, wide-tracked eyebrow as the app's section labels. */
export function eyebrowStyle(color: string = T["--color-text-muted"], size = 22): CSSProperties {
  return { fontSize: size, fontWeight: 800, letterSpacing: "0.085em", textTransform: "uppercase", color };
}

export function ShareFrame({
  brand,
  kind,
  width,
  height,
  children,
  footer = true,
  headerRight,
}: {
  brand: ShareBrandAssets;
  /** Top-right label, e.g. "Trade idea" or "Player card". */
  kind: string;
  width: number;
  height: number;
  children: ReactNode;
  footer?: boolean;
  /** Right side of the header row (the trade card's "Team A <-> Team B"). */
  headerRight?: ReactNode;
}) {
  const compact = height < 900;
  const pad = compact ? 48 : 64;
  return (
    <div
      style={{
        width,
        height,
        display: "flex",
        flexDirection: "column",
        padding: pad,
        gap: compact ? 24 : 32,
        position: "relative",
        backgroundColor: T["--color-bg"],
        fontFamily: SHARE_FONT_FAMILY,
        color: T["--color-text-primary"],
      }}
    >
      {brand.backdrop ? (
        // eslint-disable-next-line @next/next/no-img-element, jsx-a11y/alt-text
        <img src={brand.backdrop} width={width} height={height} style={{ position: "absolute", top: 0, left: 0 }} />
      ) : null}
      <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between" }}>
        <div style={{ display: "flex", flexDirection: "column", gap: compact ? 6 : 10 }}>
          {/* eslint-disable-next-line @next/next/no-img-element, jsx-a11y/alt-text */}
          <img src={brand.lockup} height={compact ? 40 : 56} width={(compact ? 40 : 56) * (1102 / 160)} />
          <div style={{ ...eyebrowStyle(T["--color-accent"], compact ? 18 : 24), letterSpacing: "0.3em" }}>{kind}</div>
        </div>
        {headerRight ? (
          <div style={{ display: "flex", alignItems: "center", gap: 14, fontSize: compact ? 26 : 34, fontWeight: 700 }}>{headerRight}</div>
        ) : null}
      </div>
      {/* space-between spreads a short card's spare height evenly between
          its blocks instead of leaving one empty band above the footer. */}
      <div style={{ display: "flex", flexDirection: "column", flexGrow: 1, justifyContent: "space-between", gap: compact ? 20 : 28 }}>
        {children}
      </div>
      {footer ? <ShareFooter brand={brand} /> : null}
    </div>
  );
}

/** White-backed QR, the same canonical site URL the mobile chrome encodes. */
export function ShareQr({ brand, size }: { brand: ShareBrandAssets; size: number }) {
  return (
    <div style={{ display: "flex", padding: Math.round(size * 0.07), backgroundColor: "#ffffff", borderRadius: shareRadius("--radius-sm") }}>
      {/* eslint-disable-next-line @next/next/no-img-element, jsx-a11y/alt-text */}
      <img src={brand.qr} width={size} height={size} />
    </div>
  );
}

function ShareFooter({ brand }: { brand: ShareBrandAssets }) {
  return (
    <div style={{ ...glassStyle(), alignItems: "center", gap: 28, padding: "18px 28px" }}>
      <ShareQr brand={brand} size={100} />
      <div style={{ display: "flex", flexDirection: "column", gap: 4, flexGrow: 1 }}>
        <div style={{ display: "flex", fontSize: 40, fontWeight: 800 }}>{BRAND_DOMAIN}</div>
        <div style={{ display: "flex", fontSize: 26, fontWeight: 500, color: T["--color-text-muted"] }}>{`Scan to try ${BRAND_NAME}`}</div>
      </div>
      {/* Mobile ShareCardChrome's tagline, same three semantic colors. */}
      <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 2, fontSize: 22, fontWeight: 900, letterSpacing: "0.12em" }}>
        <span style={{ color: T["--color-accent"] }}>PLAN.</span>
        <span style={{ color: T["--color-action"] }}>PROJECT.</span>
        <span style={{ color: T["--color-danger"] }}>WIN.</span>
      </div>
    </div>
  );
}

/** PositionBadge.tsx, squared off like the web badge. */
export function SharePositionBadge({ position, size = 22 }: { position: string | null | undefined; size?: number }) {
  if (!position) return null;
  const color = positionHex(position);
  return (
    <div
      style={{
        display: "flex",
        padding: `${Math.round(size * 0.2)}px ${Math.round(size * 0.4)}px`,
        fontSize: size,
        fontWeight: 800,
        lineHeight: 1,
        borderRadius: 0,
        backgroundColor: color ?? T["--color-surface-raised"],
        color: color ? T["--color-brand-mark-ink"] : T["--color-text-secondary"],
      }}
    >
      {position.toUpperCase()}
    </div>
  );
}

/** OvrGauge.tsx's ring (conic gradient there; an SVG arc here, since
 * Satori has no conic-gradient). Renders nothing for a null rating, same
 * "no fabricated rating" rule as OvrGauge. */
export function ShareOvrRing({ rating, size = 72 }: { rating: number | null | undefined; size?: number }) {
  if (rating === null || rating === undefined || !Number.isFinite(rating)) return null;
  const clamped = Math.max(0, Math.min(99, Math.round(rating)));
  const tint = overallRatingTintHex(clamped);
  const radius = 42;
  const circumference = 2 * Math.PI * radius;
  return (
    <div style={{ display: "flex", position: "relative", width: size, height: size, alignItems: "center", justifyContent: "center" }}>
      <svg width={size} height={size} viewBox="0 0 100 100" style={{ position: "absolute", top: 0, left: 0 }}>
        <circle cx="50" cy="50" r={radius} fill={T["--color-surface-primary"]} stroke={T["--color-border"]} strokeWidth="11" />
        <circle
          cx="50"
          cy="50"
          r={radius}
          fill="none"
          stroke={tint}
          strokeWidth="11"
          strokeLinecap="round"
          strokeDasharray={`${(clamped / 100) * circumference} ${circumference}`}
          transform="rotate(-90 50 50)"
        />
      </svg>
      <div style={{ display: "flex", fontSize: Math.round(size * 0.36), fontWeight: 900, color: tint, lineHeight: 1 }}>{clamped}</div>
    </div>
  );
}

/** PlayerAvatar.tsx: Sleeper headshot inside the tier-colored prestige
 * ring, or a plain ringed disc when there's no photo. */
export function ShareAvatar({
  src,
  tier,
  size,
  fallbackText = "",
}: {
  src: string | null;
  tier?: string | null;
  size: number;
  fallbackText?: string;
}) {
  const ring = tierHex(tier) ?? T["--color-border-strong"];
  const border = size >= 120 ? 7 : size >= 64 ? 4 : 3;
  // The prestige glow only on the hero-size avatar: blurred shadows are
  // slow to rasterize, and at row size the ring alone reads the same.
  const glow = tier && size >= 120 ? `0 0 ${Math.round(size * 0.18)}px ${withAlpha(ring, 0.45)}` : "none";
  const style: CSSProperties = {
    width: size,
    height: size,
    borderRadius: size,
    border: `${border}px solid ${ring}`,
    boxShadow: glow,
    backgroundColor: T["--color-surface-primary"],
  };
  if (src) {
    // eslint-disable-next-line @next/next/no-img-element, jsx-a11y/alt-text
    return <img src={src} width={size} height={size} style={{ ...style, objectFit: "cover", objectPosition: "top" }} />;
  }
  return (
    <div
      style={{
        ...style,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontSize: Math.round(size * 0.34),
        fontWeight: 800,
        color: T["--color-text-muted"],
      }}
    >
      {fallbackText}
    </div>
  );
}

export function initials(name: string | null | undefined): string {
  return (name ?? "")
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");
}

/** Bordered uppercase pill — the value-edge band / tier chip treatment. */
export function ShareChip({ label, color, size = 22 }: { label: string; color: string; size?: number }) {
  return (
    <div
      style={{
        display: "flex",
        padding: `${Math.round(size * 0.35)}px ${Math.round(size * 0.7)}px`,
        border: `2px solid ${color}`,
        borderRadius: 999,
        backgroundColor: withAlpha(color.startsWith("#") ? color : T["--color-text-secondary"], 0.12),
        ...eyebrowStyle(color, size),
      }}
    >
      {label}
    </div>
  );
}

export function formatValue(score: number | null | undefined): string {
  if (score === null || score === undefined || !Number.isFinite(score)) return "";
  return Math.round(score).toLocaleString("en-US");
}
