/**
 * THE sub-line ladder (docs/ui-patterns.md, "Never ellipsize"): the line under a player name (TEAM · Age · Bye · PROJ) is
 * never cut with an ellipsis. When it does not fit the width it has, whole parts leave in a fixed order: Age first, then the
 * team, then a Bye that is not close. The projection, the status, a bye that is soon (the warning tone) and any caller stat
 * never leave. If only those remain and still do not fit, the line wraps onto a second line (every part is nowrap, so a
 * part is never split). Web (ui/PlayerMetaLine.tsx) and app (components/PlayerMetaLine.tsx) both measure the width they
 * got and call this one function, so the two platforms drop the same parts at the same width.
 */
export type MetaPart = { key: string; text: string; tone?: string };

/** Lowest rung first: the first key here that is present leaves first. */
export const META_DROP_ORDER = ["age", "team", "bye"] as const;

/** A generous per-character width as a fraction of the font size (bold digits and capitals run wide), plus the " · " joint. */
const CHAR_EM = 0.62;
const JOINT_EM = 1.1;

export function estimateMetaWidth(parts: readonly MetaPart[], fontPx: number): number {
  const chars = parts.reduce((n, p) => n + p.text.length, 0);
  return chars * CHAR_EM * fontPx + Math.max(0, parts.length - 1) * JOINT_EM * fontPx;
}

/** Can this part ever leave? Never a warning-tone part (a bye that is soon) and never a key outside the ladder. */
function droppable(part: MetaPart): boolean {
  return (META_DROP_ORDER as readonly string[]).includes(part.key) && part.tone !== "warning";
}

/** The parts that fit `availablePx` after dropping in ladder order (all of them when width is unknown). */
export function fitMetaParts(parts: readonly MetaPart[], availablePx: number | null | undefined, fontPx = 12): MetaPart[] {
  if (availablePx == null || !(availablePx > 0)) return [...parts];
  let kept = [...parts];
  for (const key of META_DROP_ORDER) {
    if (estimateMetaWidth(kept, fontPx) <= availablePx) break;
    const at = kept.findIndex((p) => p.key === key && droppable(p));
    if (at >= 0) kept = kept.filter((_, i) => i !== at);
  }
  return kept;
}

/** Keys for the plain "TEAM, Age n, BYE n" strings of playerRowModel (no caller keys): so the ladder knows which is which. */
export function metaPartsFromStrings(meta: readonly string[]): MetaPart[] {
  return meta.map((text, i) => ({ key: /^age\b/i.test(text) ? "age" : /^bye\b/i.test(text) ? "bye" : i === 0 && !/\d/.test(text) && text.length <= 4 ? "team" : `m${i}`, text }));
}
