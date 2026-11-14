/**
 * Text for the round pick badge (PickAvatar): "R1" with the overall pick number small underneath when known.
 * Twin of mobile/src/lib/pickBadge.ts. Nothing is invented: no round and no pick number is just "PICK".
 */
export interface PickBadgeInput {
  round?: number | string | null;
  pickNo?: number | string | null;
  /** Free text such as "2027 Round 1", "2028 R2" or "2026 2nd round"; the round is read from it when `round` is missing. */
  label?: string | null;
}

export interface PickBadge {
  top: string;
  bottom: string | null;
  year: string | null;
  /** Spoken name, e.g. "Round 1 pick 3". */
  a11y: string;
}

export function roundFromLabel(label: string | null | undefined): string | null {
  if (!label) return null;
  const m = /\bround\s*(\d{1,2})\b/i.exec(label) ?? /\bR(\d{1,2})\b/.exec(label) ?? /\b(\d{1,2})(?:st|nd|rd|th)\s*(?:round|rd)?\b/i.exec(label.replace(/\b20\d{2}\b/g, ""));
  return m ? String(Number(m[1])) : null;
}

export function yearFromLabel(label: string | null | undefined): string | null {
  const m = label ? /\b(20\d{2})\b/.exec(label) : null;
  return m ? m[1] : null;
}

export function pickBadge({ round, pickNo, label }: PickBadgeInput): PickBadge {
  const r = round != null && String(round).trim() !== "" && String(round) !== "0" ? String(round) : roundFromLabel(label);
  const n = pickNo != null && String(pickNo).trim() !== "" && String(pickNo) !== "0" ? String(pickNo) : null;
  const top = r ? `R${r}` : n ? `#${n}` : "PICK";
  const bottom = r && n ? `#${n}` : null;
  const a11y = r ? `Round ${r} pick${n ? ` ${n}` : ""}` : n ? `Pick ${n}` : "Draft pick";
  return { top, bottom, year: yearFromLabel(label), a11y };
}
