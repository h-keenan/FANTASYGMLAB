// Shared (web + mobile twin, byte-identical): pure tab plans for the real-league quick-view sheets, so the same
// sheet groups the same content under the same tab names on both platforms. Import-free. Fantasy Sim sheets keep their
// own plans (SimPlayerSheet / SimGameTeamSheet); nothing here knows about the sim or about real news.

export interface SheetTabPlan {
  key: string;
  label: string;
}

export interface ManagerProfileTabInput {
  /** The free roster profile (strengths, needs, trade targets) is loaded. */
  hasProfile: boolean;
  /** Number of readable tendency signals (0 when not Premium or not enough history). */
  tendencyCount: number;
  /** Number of recent trades. */
  tradeCount: number;
}

/**
 * Manager profile: Overview (who they are: the free roster profile and the trade sample), Tendencies (the signals with
 * their evidence), Trades (recent trades). A tab with nothing to show is dropped, but Overview always exists so the
 * sheet is never empty (it carries the loading / upgrade / empty states).
 */
export function managerProfileTabs(input: ManagerProfileTabInput): SheetTabPlan[] {
  const tabs: SheetTabPlan[] = [{ key: "overview", label: "Overview" }];
  if (input.tendencyCount > 0) tabs.push({ key: "tendencies", label: "Tendencies" });
  if (input.tradeCount > 0) tabs.push({ key: "trades", label: "Trades" });
  return tabs;
}

export interface PercentileTabInput {
  /** The full pool is loaded (a bucket can be listed and searched). */
  hasFullPool: boolean;
  mineCount: number;
}

/**
 * Percentile explorer: the chart, metric pills and comparison stay above the tabs (they are the interaction); the lists
 * under them are Bucket (who sits where you scrubbed; a hint until you scrub, so the tab set never changes under a scrub), Find (search to add a player), Mine (your roster here).
 */
export function percentileTabs(input: PercentileTabInput): SheetTabPlan[] {
  const tabs: SheetTabPlan[] = [];
  if (input.hasFullPool) tabs.push({ key: "bucket", label: "In this bucket" });
  if (input.hasFullPool) tabs.push({ key: "find", label: "Find a player" });
  if (input.mineCount > 0) tabs.push({ key: "mine", label: "My roster" });
  return tabs;
}

/**
 * No layout jump between tabs: a tabbed surface keeps the tallest panel height it has shown (per open sheet) as the
 * minimum for the next one. Returns the new minimum given the previous one and a freshly measured panel height.
 */
export function nextPanelMinHeight(previous: number, measured: number): number {
  if (!Number.isFinite(measured) || measured <= 0) return previous;
  return Math.max(previous, Math.ceil(measured));
}
