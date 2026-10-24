/**
 * Design tokens for the server-rendered share-card PNGs (next/og's
 * ImageResponse, i.e. Satori). Satori can't resolve CSS custom properties
 * or `color-mix()`, so the card needs literal values. They are the SAME
 * token names and values as globals.css's dark `:root` (share images are
 * always dark, like mobile's fixed-dark ShareCardChrome), not a second
 * palette: tokens.test.ts parses globals.css and fails if any value here
 * drifts from it.
 */

import { positionColorVar } from "@/lib/playerPresentation";
import { resolvePlayerTier } from "@/lib/playerTier";

export const SHARE_TOKEN_HEX = {
  "--color-bg": "#000000",
  "--color-surface-primary": "#1f2226",
  "--color-surface-raised": "#3d4248",
  "--color-text-primary": "#f7f8fa",
  "--color-text-secondary": "#e5e7eb",
  "--color-text-muted": "#a8adb7",
  "--color-border": "#2a2e35",
  "--color-border-strong": "#64748b",
  "--color-brand-mark-ink": "#0b1220",
  "--color-accent": "#67e8f9",
  "--color-accent-strong": "#22d3ee",
  "--color-accent-soft": "rgba(103, 232, 249, 0.14)",
  "--color-success": "#22c55e",
  "--color-action": "#facc15",
  "--color-warning": "#f59e0b",
  "--color-danger": "#ef4444",
  "--color-success-soft": "rgba(34, 197, 94, 0.15)",
  "--color-danger-soft": "rgba(239, 68, 68, 0.15)",
  "--color-tier-generational": "#78f2d5",
  "--color-tier-elite": "#ef6cef",
  "--color-tier-impact-starter": "#f06233",
  "--color-tier-starter": "#b2c766",
  "--color-tier-contributor": "#d7dbe2",
  "--color-tier-committee-role": "#51c534",
  "--color-tier-depth-developmental": "#626a75",
  "--color-position-qb": "#fb7185",
  "--color-position-rb": "#4ade80",
  "--color-position-wr": "#38bdf8",
  "--color-position-te": "#fb923c",
  "--color-position-k": "#a78bfa",
  "--color-position-dst": "#d4d4d8",
  "--color-position-dl": "#f472b6",
  "--color-position-lb": "#2dd4bf",
  "--color-position-db": "#818cf8",
  "--color-position-flex": "#d4d4d8",
  "--radius-sm": "10px",
  "--radius-md": "14px",
  "--radius-lg": "20px",
  "--radius-panel": "20px",
} as const;

export type ShareTokenName = keyof typeof SHARE_TOKEN_HEX;

/** Aliases globals.css defines as `var(--other)` rather than a literal. */
const TOKEN_ALIASES: Record<string, ShareTokenName> = {
  "--color-premium": "--color-action",
  "--color-information": "--color-accent",
};

export function tokenValue(name: string): string | undefined {
  const resolved = (TOKEN_ALIASES[name] ?? name) as ShareTokenName;
  return SHARE_TOKEN_HEX[resolved];
}

/** "var(--color-success)" (the form the web presentation helpers return,
 * e.g. fairnessBandColor) -> its literal value, so share cards reuse those
 * helpers instead of restating their color decisions. */
export function resolveTokenColor(value: string, fallback: string = SHARE_TOKEN_HEX["--color-text-secondary"]): string {
  const match = /^var\((--[a-z0-9-]+)\)$/i.exec(value.trim());
  if (!match) return value;
  return tokenValue(match[1]) ?? fallback;
}

/** Radii are 1.5x the CSS px values: the 1080px-wide card is shown on a
 * phone at roughly 1/2.5 scale, so 1.5x keeps corners reading the same as
 * the in-app glass panels. */
export function shareRadius(name: "--radius-sm" | "--radius-md" | "--radius-lg" | "--radius-panel"): number {
  return Math.round(parseInt(SHARE_TOKEN_HEX[name], 10) * 1.5);
}

function hexToRgb(hex: string): [number, number, number] {
  const clean = hex.replace("#", "");
  return [0, 2, 4].map((offset) => parseInt(clean.slice(offset, offset + 2), 16)) as [number, number, number];
}

function rgbToHex([r, g, b]: [number, number, number]): string {
  return `#${[r, g, b].map((channel) => Math.round(channel).toString(16).padStart(2, "0")).join("")}`;
}

/** `color-mix(in srgb, a pct%, b)` for literal hex values. */
export function mixHex(a: string, b: string, aPercent: number): string {
  const weight = Math.max(0, Math.min(100, aPercent)) / 100;
  const ra = hexToRgb(a);
  const rb = hexToRgb(b);
  return rgbToHex([0, 1, 2].map((i) => ra[i] * weight + rb[i] * (1 - weight)) as [number, number, number]);
}

/** Literal-hex twin of playerPresentation.overallRatingTint (same
 * red -> gold -> green math over the same tokens). */
export function overallRatingTintHex(rating: number): string {
  const clamped = Math.max(0, Math.min(100, Math.round(rating)));
  const premium = SHARE_TOKEN_HEX["--color-action"];
  if (clamped <= 50) {
    return mixHex(premium, SHARE_TOKEN_HEX["--color-danger"], Math.round((clamped / 50) * 100));
  }
  return mixHex(SHARE_TOKEN_HEX["--color-success"], premium, Math.round(((clamped - 50) / 50) * 100));
}

export function positionHex(position: string | null | undefined): string | undefined {
  const colorVar = positionColorVar(position);
  return colorVar ? tokenValue(colorVar) : undefined;
}

export function tierHex(tier: string | null | undefined): string | undefined {
  if (!tier) return undefined;
  return tokenValue(resolvePlayerTier(tier).colorVar);
}

/** Hex + alpha -> rgba(), for the soft glows/tints the glass frame uses. */
export function withAlpha(hex: string, alpha: number): string {
  const [r, g, b] = hexToRgb(hex);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}
