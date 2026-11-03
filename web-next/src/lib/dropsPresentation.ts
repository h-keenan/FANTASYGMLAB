/**
 * Presentation helpers for Suggested Drops and the roster-value team-need
 * model (modules/drop_candidates.py, modules/roster_value_model.py). Pure
 * formatting of already-final server values: no ranking, no thresholds, no
 * lineup math lives here. Mirrored in mobile/src/lib/dropsPresentation.ts.
 */

import type { DropEffect, DropPlayer, ModelStatus, NeedsModel, NeedsPosition, RosterOverflow } from "./api";

export function ordinal(n: number): string {
  const mod100 = n % 100;
  if (mod100 >= 10 && mod100 <= 20) return `${n}th`;
  const suffix = ({ 1: "st", 2: "nd", 3: "rd" } as Record<number, string>)[n % 10] ?? "th";
  return `${n}${suffix}`;
}

/** "+4 lineup pts over 9 weeks" / "No lineup change". */
export function lineupEffectText(effect: DropEffect): string {
  const pts = effect.lineup_points_ros;
  if (Math.abs(pts) < 0.5) return "No lineup change";
  const sign = pts > 0 ? "+" : "-";
  return `${sign}${Math.abs(Math.round(pts))} lineup pts over ${effect.weeks} weeks`;
}

/** "Value +1,263" / "Value -412" (add minus drop); empty when it is noise. */
export function valueEffectText(effect: DropEffect): string {
  const v = Math.round(effect.value_delta);
  if (Math.abs(v) < 100) return "";
  return `Value ${v > 0 ? "+" : "-"}${Math.abs(v).toLocaleString("en-US")}`;
}

export function dropActionLabel(player: DropPlayer): string {
  return player.action === "move_to_ir" ? "Move to IR" : "Drop";
}

/** The header "Team need" stat. "Covered" only when the model says so; "—" when it failed. */
export function teamNeedStat(data: { needs_model?: NeedsModel | null; needed_positions: string[] }): string {
  const model = data.needs_model;
  if (model) return model.biggest_need ?? "Covered";
  return data.needed_positions.length > 0 ? data.needed_positions.join("/") : "—";
}

/** The sentence under the Priority Adds heading: the model's headline, or the
 * legacy line when the model failed (the "Limited data" note says so). */
export function needsHeadline(data: { needs_model?: NeedsModel | null; needed_positions: string[] }): string {
  if (data.needs_model?.headline) return data.needs_model.headline;
  const positions = data.needed_positions.map((p) => p.toUpperCase()).filter(Boolean);
  return positions.length > 0 ? `Current need: ${positions.join(" / ")}.` : "Needs could not be fully modeled right now.";
}

export function needTierLabel(tier: NeedsPosition["tier"]): string {
  return { primary: "Need", secondary: "Need", watch: "Watch", covered: "Covered" }[tier];
}

export function weakestSlotText(position: NeedsPosition): string {
  const slot = position.weakest_slot;
  return `${slot.slot} · ${ordinal(slot.rank)} of ${slot.of}`;
}

export function upgradeText(position: NeedsPosition): string {
  const up = position.upgrade;
  if (!up.name || up.ppw < 0.1) return "No free agent helps";
  return `${up.name} +${up.ppw.toFixed(1)} pts/wk`;
}

/** "Limited data: ..." from the model_status markers; null when nothing degraded. */
export function limitedDataNote(status: ModelStatus | null | undefined): string | null {
  if (!status?.degraded || status.reasons.length === 0) return null;
  return `Limited data: ${status.reasons.map((r) => r.message).join(" ")}`;
}

/** "You'd have to drop 2: A, B" for a trade that overfills the roster. */
export function overflowHeadline(overflow: RosterOverflow): string {
  const count = `${overflow.need} player${overflow.need === 1 ? "" : "s"}`;
  if (overflow.unavailable) return `This trade puts you ${overflow.need} over the roster limit, and the cuts could not be named safely.`;
  if (!overflow.satisfied) return `This trade puts you ${overflow.need} over the roster limit and there are not enough safe cuts: you would have to drop starters or protected players.`;
  return `This trade puts you over the roster limit: you'd have to drop ${count}: ${overflow.drops.map((d) => d.name).join(", ")}.`;
}
