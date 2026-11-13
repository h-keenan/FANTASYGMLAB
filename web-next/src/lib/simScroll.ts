// Twin file: web-next/src/lib/simScroll.ts and mobile/src/lib/simScroll.ts stay identical.

/**
 * What the player is looking at, as one string: a change of it is a "new page", so the screen scrolls
 * back to the top (instantly) instead of keeping the previous page's scroll offset (the weekly recap
 * used to open halfway down). A refresh of the same page (same key) never scrolls.
 */
export function simScrollKey(parts: { view: string; stage?: string | null; tab?: string | null; recapIndex?: number; hasRecap?: boolean; draftRecap?: boolean; week?: number | null; status?: string | null; step?: string | null }): string {
  return [parts.view, parts.stage ?? "", parts.tab ?? "", parts.hasRecap ? `recap${parts.recapIndex ?? 0}` : "", parts.draftRecap ? "draftrecap" : "", parts.week ?? "", parts.status ?? "", parts.step ?? ""].join("|");
}

/** Scroll to the top only when the page changed (never on the first render, never for the same key). */
export function simShouldScrollTop(previousKey: string | null, nextKey: string): boolean {
  return previousKey !== null && previousKey !== nextKey;
}

/** Stage-advancing primary actions of the footer bars. */
export type SimStageAction = "start_rookie_draft" | "auto_draft" | "start_season" | "start_playoffs";

/**
 * Where the player lands after a stage-advancing action: the page that hosts the new stage. The offseason
 * overview ("home" while the game is in its offseason) holds the rookie draft and cut-down; the in-season
 * Home holds the new week. Without this the player stayed on Team/Trades/League while the stage changed.
 */
export function simTabAfterStageAction(_action: SimStageAction): "home" {
  return "home";
}
