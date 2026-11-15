import type { HistoryTransaction, RecapStory } from "./api";

/**
 * League Recaps / History (Revision 13) presentation helpers.
 *
 * Reads only fields the backend already computes (modules.league_recaps /
 * modules.league_history / modules.transaction_grades) — no scoring math,
 * grading, or recap-story generation lives here, only formatting, mirroring modules/league_recaps_ui.py and
 * modules/league_history_ui.py exactly.
 */

// modules/league_recaps.py's STORY_* constants, verbatim.
export const STORY_WAIVER = "waiver";
export const STORY_WAIVER_LOW = "waiver_low";
export const STORY_TRADE = "trade";
export const STORY_ACTIVITY = "activity";
export const STORY_ACTIVITY_LOW = "activity_low";

/**
 * CTA label for a story's History deep link — modules/league_recaps_ui.py's
 * history_deep_link_label(), verbatim. History (the transaction timeline)
 * only has trade/waiver/free-agent/pick records, so performance and
 * matchup stories (score-based, not transaction-based) never link out —
 * porting that gate exactly rather than offering a broken link.
 */
export function historyDeepLinkLabel(story: RecapStory): string {
  if (story.story_type === STORY_TRADE) return "View Trade History";
  if (story.story_type === STORY_WAIVER || story.story_type === STORY_WAIVER_LOW) return "View waiver history";
  if (story.story_type === STORY_ACTIVITY || story.story_type === STORY_ACTIVITY_LOW) return "Open League History";
  return "";
}

// --- History tab -----------------------------------------------------

// modules/league_history.py's FILTER_* constants + HISTORY_FILTERS tuple,
// verbatim (the exact pill set the web app's History route renders).
export const FILTER_ALL = "All";
export const FILTER_TRADES = "Trades";
export const FILTER_WAIVERS = "Waivers";
export const FILTER_FREE_AGENTS = "Free Agents";
export const FILTER_WIRE = "Waivers / Free Agents";
export const FILTER_PICKS = "Draft picks";
export const FILTER_OTHER = "Other moves";
export const HISTORY_FILTERS: readonly string[] = [FILTER_ALL, FILTER_TRADES, FILTER_WIRE, FILTER_PICKS, FILTER_OTHER];

// modules/league_history.py's matches_history_filter(), verbatim.
export function matchesHistoryFilter(transaction: HistoryTransaction, selected: string): boolean {
  const label = selected || FILTER_ALL;
  const txType = transaction.type;
  if (label === FILTER_ALL || label === "") return true;
  if (label === FILTER_TRADES) return txType === "trade";
  if (label === FILTER_WAIVERS) return txType === "waiver";
  if (label === FILTER_FREE_AGENTS) return txType === "free_agent";
  if (label === FILTER_WIRE) return txType === "waiver" || txType === "free_agent";
  if (label === FILTER_PICKS) return Boolean(transaction.draft_picks?.length);
  if (label === FILTER_OTHER) {
    return txType !== "trade" && txType !== "waiver" && txType !== "free_agent" && !transaction.draft_picks?.length;
  }
  return true;
}

// A recap story's history_filter (e.g. "Waivers") may not be one of the
// five rendered pills above (modules/league_recaps.py uses the narrower
// FILTER_WAIVERS/FILTER_TRADES/FILTER_ALL labels for its deep links, while
// the pill row only ever renders FILTER_WIRE for the combined waiver/
// free-agent pill) — map the deep link onto the pill that actually
// contains it so the filtered result and the highlighted pill agree.
export function historyFilterToPill(filter: string): string {
  if (filter === FILTER_TRADES) return FILTER_TRADES;
  if (filter === FILTER_WAIVERS || filter === FILTER_FREE_AGENTS || filter === FILTER_WIRE) return FILTER_WIRE;
  if (filter === FILTER_PICKS) return FILTER_PICKS;
  if (filter === FILTER_OTHER) return FILTER_OTHER;
  return FILTER_ALL;
}

// modules/league_history_ui.py's empty_filter_note(), verbatim.
export function emptyFilterNote(selected: string): string {
  const label = selected || FILTER_ALL;
  if (label === FILTER_TRADES) return "No completed trades in this season.";
  if (label === FILTER_WAIVERS) return "No waiver claims in this season.";
  if (label === FILTER_FREE_AGENTS) return "No free-agent adds in this season.";
  if (label === FILTER_WIRE) return "No waiver claims or free-agent adds in this season.";
  if (label === FILTER_PICKS) return "No draft picks changed hands in this season.";
  if (label === FILTER_OTHER) return "No other recorded moves in this season.";
  return "No completed transactions yet for this season.";
}

// modules/league_history.py's format_history_when(), verbatim.
export function formatHistoryWhen(week: number, timestampMs: number): string {
  const parts: string[] = [];
  if (week > 0) parts.push(`Week ${week}`);
  if (timestampMs > 0) {
    const instant = new Date(timestampMs);
    if (!Number.isNaN(instant.getTime())) {
      const month = instant.toLocaleString("en-US", { month: "short", timeZone: "UTC" });
      parts.push(`${month} ${instant.getUTCDate()}, ${instant.getUTCFullYear()}`);
    }
  }
  return parts.length ? parts.join(" · ") : "Date unavailable";
}

export const TYPE_KICKERS: Record<string, string> = {
  trade: "Trade",
  waiver: "Waiver",
  free_agent: "Free agent",
};

// modules/transaction_grades.py's _tone_for_letter() output ->
// modules/league_history_styles.py's .dg-tx-grade--* color rules, verbatim.
export function gradeToneColorVar(tone: string | undefined): string {
  if (tone === "success") return "var(--color-success)";
  if (tone === "positive" || tone === "accent") return "var(--color-information)";
  if (tone === "warning" || tone === "risk") return "var(--color-warning)";
  if (tone === "pending") return "var(--color-text-muted)";
  return "var(--color-text-secondary)";
}

export function pickLabel(asset: { season?: string; round?: number | null; label?: string }): string {
  if (asset.season && asset.round) return `${asset.season} Round ${asset.round}`;
  return asset.label || "Draft pick";
}
