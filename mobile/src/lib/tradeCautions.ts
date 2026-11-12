/** Trade Analyzer caution tags (modules/trade_cautions.py). The server owns
 * the wording and sends it in `verdict.cautions`; web and mobile render these
 * helpers verbatim so the tag, its one-line explanation and the share card
 * line read identically on every surface. Identical twin: keep this file
 * byte-identical in web-next/src/lib and mobile/src/lib. */

export interface TradeCaution {
  /** Stable id, e.g. "pick_glut". */
  code: string;
  /** Short tag, e.g. "Trading proven value for picks you may not need". */
  tag: string;
  /** One-line reason. The value numbers are never changed by a caution. */
  explanation: string;
  /** True when the verdict label was eased one step because of this caution. */
  softened?: boolean;
  /** The label before softening, e.g. "SMASH ACCEPT". */
  softened_from?: string;
  facts?: Record<string, unknown>;
}

export interface VerdictWithCautions {
  band?: string;
  cautions?: TradeCaution[] | null;
}

/** Well-formed cautions only (older servers omit the field). */
export function verdictCautions(verdict: VerdictWithCautions | null | undefined): TradeCaution[] {
  const list = verdict?.cautions;
  if (!Array.isArray(list)) return [];
  return list.filter((c) => c && typeof c.tag === "string" && c.tag.trim() !== "");
}

function titleCase(label: string): string {
  return label
    .toLowerCase()
    .split(/\s+/)
    .map((w) => (w ? w[0].toUpperCase() + w.slice(1) : w))
    .join(" ");
}

/** The explanation line shown under the tag, with the label note when the
 * verdict was softened (so the label and the copy always agree). */
export function cautionDetail(caution: TradeCaution, verdictBand?: string): string {
  const base = (caution.explanation || "").trim();
  if (!caution.softened || !caution.softened_from) return base;
  const now = verdictBand ? titleCase(verdictBand) : "Accept";
  return `${base} Label eased one step, from ${titleCase(caution.softened_from)} to ${now}.`.trim();
}

/** One sentence for plain-text and image share output: the tag, so a shared
 * label never hides why it was softened. Empty when there is no caution. */
export function cautionShareLine(verdict: VerdictWithCautions | null | undefined): string {
  const tags = verdictCautions(verdict).map((c) => c.tag.trim().replace(/[.\s]+$/, ""));
  return tags.length ? `${tags.join("; ")}.` : "";
}
