import type { ProspectScoutingAggregate } from "@/lib/api";

/**
 * College Scouting (Revision 20) presentation helpers — ports
 * modules/college_scouting_ui.py's `_aggregate_text` and
 * modules/college_scouting.py's `_confidence_label` thresholds verbatim
 * (MIN_SCOUTS_FOR_MEDIUM_CONFIDENCE=3, MIN_SCOUTS_FOR_FULL_CONFIDENCE=8).
 * The shared GET /v1/scouting/prospects response only sends the raw
 * avg_grade/scout_count/avg_round_projection numbers (no confidence_label
 * field) — this derives the same high/medium/low label client-side from
 * scout_count alone, matching the Python module's own derivation exactly,
 * not inventing a new taxonomy.
 */

const MIN_SCOUTS_FOR_MEDIUM_CONFIDENCE = 3;
const MIN_SCOUTS_FOR_FULL_CONFIDENCE = 8;

export type ScoutingConfidenceLabel = "high" | "medium" | "low";

export function scoutingConfidenceLabel(scoutCount: number): ScoutingConfidenceLabel {
  if (scoutCount >= MIN_SCOUTS_FOR_FULL_CONFIDENCE) return "high";
  if (scoutCount >= MIN_SCOUTS_FOR_MEDIUM_CONFIDENCE) return "medium";
  return "low";
}

/** "4.2 avg · 5 scouts" / "Not yet scouted" — byte-for-byte match of
 * modules/college_scouting_ui.py's `_aggregate_text`. */
export function aggregateText(aggregate: ProspectScoutingAggregate): string {
  const { avg_grade: avgGrade, scout_count: scoutCount } = aggregate;
  if (avgGrade == null || scoutCount === 0) return "Not yet scouted";
  return `${avgGrade.toFixed(1)} avg · ${scoutCount} ${scoutCount === 1 ? "scout" : "scouts"}`;
}

/** "Ole Miss · 2026 class" / "2026 class" / "Ole Miss" — mirrors
 * modules/college_scouting_ui.py's `_prospect_card_html` class_bits. */
export function classLabel(school: string, draftYear: number | null): string {
  if (school && draftYear) return `${school} · ${draftYear} class`;
  if (draftYear) return `${draftYear} class`;
  return school;
}
