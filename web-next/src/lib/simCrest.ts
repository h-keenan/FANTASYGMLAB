/**
 * Fantasy Sim: generated team emblems. A team name deterministically picks a
 * shape, a pattern, a color pair and a letter, so every team keeps the same
 * crest everywhere (standings, matchup, trades, feed, scouting sheet) with no
 * stored art. Original artwork: simple geometric shields/badges, never a
 * real franchise's mark.
 *
 * Pure and import-free, so web (inline SVG) and the app (react-native-svg)
 * render the same description (byte-identical twin, scripts/check_lib_twins.mjs).
 * Coordinates are in a 64x64 box.
 */

export type SimCrestShape = "shield" | "round" | "diamond" | "hex" | "pennant" | "banner";
export type SimCrestPattern = "solid" | "stripe" | "chevron" | "split" | "bar";

export interface SimCrestSpec {
  shape: SimCrestShape;
  pattern: SimCrestPattern;
  /** Field color. */
  primary: string;
  /** Pattern and rim color. */
  secondary: string;
  /** Letter color, picked for contrast against the field. */
  ink: string;
  /** Halo behind the letter so it stays readable over the pattern. */
  halo: string;
  letter: string;
}

export interface SimCrestArt {
  viewBox: string;
  outline: string;
  /** Pattern shape (clipped to the outline by the renderer), or null for solid. */
  pattern: string | null;
  letter: string;
  letterX: number;
  letterY: number;
  letterSize: number;
}

// Emblem artwork palette (not UI tokens): [field, accent] pairs chosen to read
// on both the dark and light surfaces.
const PALETTE: [string, string][] = [
  ["#1d4ed8", "#facc15"],
  ["#b91c1c", "#f8fafc"],
  ["#047857", "#fde68a"],
  ["#6d28d9", "#fbbf24"],
  ["#0e7490", "#fb923c"],
  ["#be185d", "#fef3c7"],
  ["#334155", "#38bdf8"],
  ["#c2410c", "#1e293b"],
  ["#15803d", "#f1f5f9"],
  ["#4338ca", "#34d399"],
  ["#a16207", "#0f172a"],
  ["#9f1239", "#fda4af"],
  ["#0369a1", "#e0f2fe"],
  ["#4d7c0f", "#facc15"],
];
const SHAPES: SimCrestShape[] = ["shield", "round", "diamond", "hex", "pennant", "banner"];
const PATTERNS: SimCrestPattern[] = ["solid", "stripe", "chevron", "split", "bar"];

const OUTLINES: Record<SimCrestShape, string> = {
  shield: "M32 3 L57 11 V32 C57 47 46 57 32 62 C18 57 7 47 7 32 V11 Z",
  round: "M4 32 a28 28 0 1 0 56 0 a28 28 0 1 0 -56 0 Z",
  diamond: "M32 2 L62 32 L32 62 L2 32 Z",
  hex: "M32 2 L58 17 V47 L32 62 L6 47 V17 Z",
  pennant: "M7 6 H57 V38 L32 61 L7 38 Z",
  banner: "M7 5 H57 V57 L44.5 49 L32 58 L19.5 49 L7 57 Z",
};

const PATTERN_PATHS: Record<Exclude<SimCrestPattern, "solid">, string> = {
  stripe: "M25 0 H39 V64 H25 Z",
  chevron: "M0 26 L32 10 L64 26 V40 L32 24 L0 40 Z",
  split: "M0 64 L64 0 V64 Z",
  bar: "M0 40 H64 V50 H0 Z",
};

/** FNV-1a, 32 bit: stable across platforms and JS engines. */
export function simCrestHash(text: string): number {
  let h = 0x811c9dc5;
  for (let i = 0; i < text.length; i += 1) {
    h ^= text.charCodeAt(i);
    h = Math.imul(h, 0x01000193) >>> 0;
  }
  return h >>> 0;
}

const SKIP_WORDS = new Set(["the", "a", "an", "of", "team", "fc"]);

/** The crest letter: the first letter of the first meaningful word. */
export function simCrestLetter(name: string): string {
  const words = name.replace(/[^A-Za-z0-9\s'-]/g, " ").split(/\s+/).filter(Boolean);
  const word = words.find((w) => !SKIP_WORDS.has(w.toLowerCase())) ?? words[0] ?? "?";
  return word[0].toUpperCase();
}

function luminance(hex: string): number {
  const n = parseInt(hex.slice(1), 16);
  const [r, g, b] = [(n >> 16) & 255, (n >> 8) & 255, n & 255].map((v) => {
    const c = v / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

const LIGHT_INK = "#ffffff";
const DARK_INK = "#111827";

export function simCrestSpec(name: string): SimCrestSpec {
  const key = (name || "?").trim().toLowerCase();
  const h = simCrestHash(key);
  const [primary, secondary] = PALETTE[h % PALETTE.length];
  const ink = luminance(primary) > 0.3 ? DARK_INK : LIGHT_INK;
  return {
    shape: SHAPES[(h >>> 4) % SHAPES.length],
    pattern: PATTERNS[(h >>> 9) % PATTERNS.length],
    primary,
    secondary,
    ink,
    halo: ink === LIGHT_INK ? DARK_INK : LIGHT_INK,
    letter: simCrestLetter(name || "?"),
  };
}

export function simCrestArt(spec: SimCrestSpec): SimCrestArt {
  return {
    viewBox: "0 0 64 64",
    outline: OUTLINES[spec.shape],
    pattern: spec.pattern === "solid" ? null : PATTERN_PATHS[spec.pattern],
    letter: spec.letter,
    letterX: 32,
    letterY: spec.shape === "pennant" || spec.shape === "banner" ? 41 : 43,
    letterSize: 30,
  };
}

/** Plain-language description for screen readers. */
export function simCrestLabel(name: string): string {
  return `${name || "Team"} emblem`;
}
