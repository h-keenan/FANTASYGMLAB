// Shared (web + mobile twin): the saved-games rows on the Fantasy Sim hub. A row says where the season stands (phase, week
// progress, grade) and how it was set up, instead of one line of "Week 4 of 14".

import { SIM_DIFFICULTY_COPY, SIM_SCORING_LABELS, simGameLiteLine, simGradeTone, type SimGameLite, type SimGameTone, type SimScoring } from "./simGame";

export interface SimHubRow {
  /** "Week 4 of 14", "Draft in progress", "Finished · Grade B+". */
  title: string;
  /** The one chip: the phase, or the grade once finished. */
  chip: { label: string; tone: SimGameTone };
  /** Season progress as segments done / total; null while drafting. */
  progress: { done: number; total: number } | null;
  /** "12 teams · PPR · Normal". */
  meta: string;
  /** "Played today" / "Played 3d ago"; null when the date is unusable. */
  played: string | null;
  /** True when the primary affordance is "Continue" (not finished). */
  open: boolean;
}

/** "today", "yesterday", "3d ago", "2w ago". */
export function simHubAgo(iso: string | null | undefined, now: number = Date.now()): string | null {
  const t = iso ? Date.parse(iso) : NaN;
  if (!Number.isFinite(t)) return null;
  const days = Math.floor(Math.max(0, now - t) / 86_400_000);
  if (days < 1) return "today";
  if (days === 1) return "yesterday";
  if (days < 14) return `${days}d ago`;
  return `${Math.floor(days / 7)}w ago`;
}

export function simHubRow(game: SimGameLite, now: number = Date.now()): SimHubRow {
  const regular = game.settings.regular_weeks ?? 0;
  const playoff = game.settings.playoff_weeks ?? 0;
  const total = regular + playoff;
  let progress: SimHubRow["progress"] = null;
  if (game.status === "complete" && total > 0) progress = { done: total, total };
  else if (game.status === "in_season" && regular > 0) progress = { done: Math.max(0, Math.min(total, game.current_week - 1)), total };
  else if (game.status === "playoffs" && total > 0) progress = { done: Math.min(total, Math.max(regular, game.current_week - 1)), total };
  const chip: SimHubRow["chip"] =
    game.status === "complete"
      ? { label: game.grade_letter ?? "Done", tone: game.grade_letter ? simGradeTone(game.grade_letter) : "muted" }
      : game.status === "drafting"
        ? { label: "Draft", tone: "warning" }
        : game.status === "playoffs"
          ? { label: "Playoffs", tone: "warning" }
          : { label: "In season", tone: "accent" };
  const scoring = SIM_SCORING_LABELS[(game.settings.scoring ?? "ppr") as SimScoring] ?? game.settings.scoring ?? "PPR";
  const meta = [`${game.settings.teams ?? 12} teams`, scoring, SIM_DIFFICULTY_COPY[game.difficulty]?.label ?? game.difficulty].filter(Boolean).join(" · ");
  const ago = simHubAgo(game.updated_at, now);
  return { title: simGameLiteLine(game), chip, progress, meta, played: ago ? `Played ${ago}` : null, open: game.status !== "complete" };
}
