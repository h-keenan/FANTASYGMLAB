/**
 * Value font size for a compact SnapshotTile. A 4-up strip at phone width
 * leaves roughly 57px of inner width per tile, so a fixed 1.25rem value
 * ("36,414", "-6,862") touched or overflowed the tile edges. Step the size
 * down by rendered length so up to 7 characters ("-12,345") fit at 360px.
 */
export function compactValueFontSize(value: string): string {
  const len = Array.from(value).length;
  if (len <= 4) return "1.25rem";
  if (len === 5) return "1.125rem";
  if (len === 6) return "0.9375rem";
  if (len === 7) return "0.8125rem";
  return "0.75rem";
}
