/**
 * Players page as templates (docs/ui-patterns.md "Module templates"): the collapsed summary of the draft-pick module that
 * replaced the Players | Picks toggle (a second tab row). Import-light, byte-identical twin of mobile/src/lib/playersModules.ts.
 */
import type { CompactPart } from "./compactModule";

export interface PickSummaryInput {
  label: string | null;
  season: number | string | null;
  score: number | null;
}

/** "12 picks · 2026-2028 · Top 2026 1st". */
export function picksSummaryParts(picks: ReadonlyArray<PickSummaryInput>): CompactPart[] {
  if (picks.length === 0) return [{ key: "none", text: "No draft-pick assets yet", tone: "muted" }];
  const seasons = picks.map((p) => Number(p.season)).filter((n) => Number.isFinite(n) && n > 0);
  const lo = seasons.length ? Math.min(...seasons) : null;
  const hi = seasons.length ? Math.max(...seasons) : null;
  const top = [...picks].sort((a, b) => (b.score ?? -Infinity) - (a.score ?? -Infinity))[0];
  const parts: Array<CompactPart | null> = [
    { key: "count", text: `${picks.length} pick${picks.length === 1 ? "" : "s"}`, strong: true },
    lo != null && hi != null ? { key: "seasons", text: lo === hi ? String(lo) : `${lo}-${hi}` } : null,
    top?.label ? { key: "top", text: `Top ${top.label}`, tone: "accent" } : null,
  ];
  return parts.filter((p): p is CompactPart => p != null);
}
