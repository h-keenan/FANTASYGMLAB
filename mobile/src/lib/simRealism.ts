// Shared (web + mobile twin): the Realism update's copy and view logic. A save made before newer rules (honest draft help, realistic NFL
// usage, aging and retirement, fresh rookie names, ...) keeps playing by the old ones; the update appends one event to the game's log that
// switches the missing rules on from a boundary onward. Pure: the rows and per-rule wording come from the server (`game.rules`), this file
// owns the framing, the toast and the banner rules. Imports types only.
import type { SimGame, SimRealismBoundary, SimRealismFlag, SimRealismInfo, SimRealismResponse } from "./simGame";

export const SIM_REALISM_MENU_TITLE = "Update game rules";
export const SIM_REALISM_SHEET_TITLE = "Update game rules";
export const SIM_REALISM_SHEET_DESCRIPTION = "Turn on the newer realism rules for this save.";
export const SIM_REALISM_CONFIRM_LABEL = "Update rules";
export const SIM_REALISM_CANCEL_LABEL = "Not now";
export const SIM_REALISM_BANNER_TITLE = "Newer realism rules are available";
export const SIM_REALISM_BANNER_CTA = "Review";
export const SIM_REALISM_BANNER_DISMISS = "Dismiss";
/** The honest limit of the update, shown wherever it is offered. Mirrors modules/sim/game_rules.NOT_RETROACTIVE. */
export const SIM_REALISM_NOT_RETROACTIVE = "Past results stay as they were; new rules apply going forward.";
export const SIM_REALISM_INTRO =
  "This game was created before these rules existed, so it still plays the old way. Updating switches them on for the rest of the game.";
export const SIM_REALISM_UNDO_NOTE = "Reset this week undoes an update made this week; going back to an earlier week undoes any update after it.";
export const SIM_REALISM_CURRENT = "This game already plays by the newest rules.";

export const SIM_REALISM_BOUNDARY_LABELS: Record<SimRealismBoundary, string> = {
  now: "Right away",
  week: "From the next simulated week",
  season: "From the next offseason",
};

/** The wording for when a rule takes effect (the server's own copy when it sent one, so a new boundary never renders blank). */
export function simRealismWhen(flag: Pick<SimRealismFlag, "boundary" | "when">): string {
  return flag.when || SIM_REALISM_BOUNDARY_LABELS[flag.boundary] || "";
}

/** The rules an update would switch on (empty when the game is current, finished, or an older server sent no `rules`). */
export function simRealismPending(game: Pick<SimGame, "rules"> | null | undefined): SimRealismFlag[] {
  const info = game?.rules;
  return info && info.eligible ? info.pending ?? [] : [];
}

/** Whether to offer the update at all: only while at least one rule is still off. */
export function simRealismEligible(game: Pick<SimGame, "rules"> | null | undefined): boolean {
  return simRealismPending(game).length > 0;
}

/** Rules in the preview list grouped by when they start, in the order Right away, Next week, Next offseason. */
export function simRealismGroups(pending: readonly SimRealismFlag[]): { boundary: SimRealismBoundary; when: string; flags: SimRealismFlag[] }[] {
  const order: SimRealismBoundary[] = ["now", "week", "season"];
  return order
    .map((boundary) => {
      const flags = pending.filter((f) => f.boundary === boundary);
      return { boundary, when: flags[0] ? simRealismWhen(flags[0]) : SIM_REALISM_BOUNDARY_LABELS[boundary], flags };
    })
    .filter((g) => g.flags.length > 0);
}

/** One line for the menu module's collapsed header. */
export function simRealismParts(info: SimRealismInfo | null | undefined): { key: string; text: string; strong?: boolean; tone?: "muted" | "warning" | "danger" | "success" }[] {
  if (!info) return [{ key: "a", text: "Not available", tone: "muted" }];
  if (info.eligible && info.pending.length > 0) {
    const n = info.pending.length;
    return [{ key: "n", text: `${n} newer rule${n === 1 ? "" : "s"} available`, strong: true }, { key: "w", text: "past results stay", tone: "muted" }];
  }
  if (info.scheduled.length > 0) {
    return [{ key: "s", text: "Updated", strong: true }, { key: "w", text: `${info.scheduled.length} rule${info.scheduled.length === 1 ? "" : "s"} start next offseason`, tone: "muted" }];
  }
  return [{ key: "c", text: "Up to date", strong: true, tone: "success" }];
}

/** The toast after a successful update (or when there was nothing to do). */
export function simRealismToast(result: Pick<SimRealismResponse, "upgraded" | "flags"> | null | undefined): string {
  if (!result || !result.upgraded) return SIM_REALISM_CURRENT;
  const n = result.flags.length;
  return `Rules updated: ${n} new rule${n === 1 ? "" : "s"} on. ${SIM_REALISM_NOT_RETROACTIVE}`;
}

/** Banner storage key: dismissed per game and per rules version, so a later update opportunity can show it again. */
export function simRealismBannerKey(gameId: string, info: Pick<SimRealismInfo, "rules_version" | "pending"> | null | undefined): string {
  const flags = (info?.pending ?? []).map((f) => f.flag).sort().join(",");
  return `sim.realism.banner.${gameId}.${info?.rules_version ?? 0}.${flags}`;
}

/** The Home banner: only for an eligible old save, and not once the user dismissed it for this exact set of rules. */
export function simRealismBanner(
  game: Pick<SimGame, "id" | "rules" | "status"> | null | undefined,
  dismissed: boolean,
): { title: string; body: string; cta: string; count: number } | null {
  if (!game || dismissed || game.status === "complete" || !simRealismEligible(game)) return null;
  const n = simRealismPending(game).length;
  return { title: SIM_REALISM_BANNER_TITLE, body: `${n} rule${n === 1 ? "" : "s"} this save is missing. ${SIM_REALISM_NOT_RETROACTIVE}`, cta: SIM_REALISM_BANNER_CTA, count: n };
}
