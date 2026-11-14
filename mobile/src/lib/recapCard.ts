/**
 * The recap card (docs/ui-patterns.md, "Recap card"): one card per story page and review block, a kicker, an optional
 * badge (a letter grade, a finish) and THREE label/value rows. Rows beyond the third are not dropped: they sit behind
 * a tap ("More") so the page stays glanceable and nothing is lost. Pure and import-free; byte-identical twin of
 * mobile/src/lib/recapCard.ts.
 */

export type RecapTone = "success" | "danger" | "warning" | "accent" | "muted";

export const RECAP_CARD_ROWS = 3;

export interface RecapCardRow {
  key: string;
  label: string;
  value: string;
  /** A smaller line under the value. */
  sub?: string | null;
  tone?: RecapTone;
}

export interface RecapCardModel {
  kicker: string;
  /** A letter grade or a finish ("A-", "Champions"); drawn as a capsule beside the kicker. */
  badge: string | null;
  rows: RecapCardRow[];
  more: RecapCardRow[];
}

export function recapCardModel(input: { kicker: string; badge?: string | null; rows: ReadonlyArray<RecapCardRow | null | undefined | false> }): RecapCardModel {
  const rows = input.rows.filter((r): r is RecapCardRow => Boolean(r && r.value && r.value.trim()));
  return { kicker: input.kicker, badge: input.badge ?? null, rows: rows.slice(0, RECAP_CARD_ROWS), more: rows.slice(RECAP_CARD_ROWS) };
}

/** The "label detail" pairs the story models already produce (`{ label, detail }` / `{ label, text }`) as rows. */
export function recapRowsFromItems(items: ReadonlyArray<{ key?: string; label: string; detail?: string; text?: string; tone?: RecapTone }>): RecapCardRow[] {
  return items.map((it, i) => ({ key: it.key ?? `${i}-${it.label}`, label: it.label, value: it.detail ?? it.text ?? "", tone: it.tone }));
}
