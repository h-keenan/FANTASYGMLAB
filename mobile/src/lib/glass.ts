/**
 * Liquid-glass surface tokens (coridian_, 2026-10-24: "lots of transparent
 * liquid-glass modules"). ONE definition of the translucent card surface the
 * whole app shares, mirroring web-next's `.glass-surface` (globals.css):
 * a translucent fill so the root AppBackground shows through, plus a faint
 * light rim. Pure data (no react-native import) so it is unit-testable.
 *
 * - `glass`: top-level module/card fill.
 * - `glassInset`: a tile nested inside a glass card (needs to read against
 *   the glass behind it, so it is a light/dark tint, not another glass).
 * - `glassBorder`: the rim for glass cards.
 *
 * No live blur per card on purpose: lists of cards with a BlurView each are
 * expensive (and Android blur is inconsistent); the ambient background is
 * what makes the translucency read. Use GlassPanel for one-off hero blur.
 */
export interface GlassTokens {
  glass: string;
  glassInset: string;
  glassBorder: string;
  /** Text input / small control fill + rim (web `.glass-input`). */
  glassInput: string;
  glassInputBorder: string;
}

export const darkGlass: GlassTokens = {
  glass: 'rgba(28,32,40,0.58)',
  glassInset: 'rgba(255,255,255,0.06)',
  glassBorder: 'rgba(255,255,255,0.14)',
  glassInput: 'rgba(255,255,255,0.05)',
  glassInputBorder: 'rgba(255,255,255,0.14)',
};

export const lightGlass: GlassTokens = {
  glass: 'rgba(255,255,255,0.68)',
  glassInset: 'rgba(10,30,45,0.05)',
  glassBorder: 'rgba(10,30,45,0.12)',
  glassInput: 'rgba(255,255,255,0.6)',
  glassInputBorder: 'rgba(10,30,45,0.12)',
};

export function parseRgba(value: string): { r: number; g: number; b: number; a: number } {
  const m = value.match(/rgba?\(([^)]+)\)/);
  if (!m) throw new Error(`not an rgba color: ${value}`);
  const [r, g, b, a = 1] = m[1].split(',').map((p) => Number(p.trim()));
  return { r, g, b, a };
}

/** Composite a translucent rgba color over an opaque hex backdrop. */
export function compositeOver(fg: string, bgHex: string): [number, number, number] {
  const { r, g, b, a } = parseRgba(fg);
  const n = parseInt(bgHex.replace('#', ''), 16);
  const bg = [(n >> 16) & 255, (n >> 8) & 255, n & 255];
  return [r, g, b].map((c, i) => Math.round(c * a + bg[i] * (1 - a))) as [number, number, number];
}

function luminance([r, g, b]: [number, number, number]): number {
  const f = (c: number) => {
    const s = c / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
}

export function contrastRatio(a: [number, number, number], b: [number, number, number]): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}
