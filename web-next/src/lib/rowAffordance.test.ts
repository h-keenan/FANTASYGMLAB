import { readdirSync, readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

import { rowAffordance } from "./rowAffordance";

describe("rowAffordance", () => {
  it("a fully tappable row has no chevron", () => {
    expect(rowAffordance({ rowAction: "player" })).toEqual({ wholeRow: true, chevron: false });
  });
  it("a chevron that repeats the row action is redundant", () => {
    expect(rowAffordance({ rowAction: "player", secondaryAction: "player" }).chevron).toBe(false);
  });
  it("a chevron for a different secondary target is allowed", () => {
    expect(rowAffordance({ rowAction: "player", secondaryAction: "bid_sheet" }).chevron).toBe(true);
  });
  it("an inert row has neither", () => {
    expect(rowAffordance({})).toEqual({ wholeRow: false, chevron: false });
  });
});

/**
 * Source scan: the only files allowed to draw a navigation chevron (web `›`/Chevron, app chevron-forward). Everything
 * else is a fully tappable row/tile/module and must not. Expand/collapse chevrons (rotating, chevron-up/down) are state
 * and are fine. Add a file here only with the reason it has a SEPARATE secondary target.
 */
const ALLOWED_NAV_CHEVRON = new Set([
  // app: bid row: tap opens the player, the chevron opens the bid sheet (separate target)
  "WaiverRecommendationCard.tsx",
  // app: expand/collapse, filter dropdown and header pickers: state/menu indicators, not row navigation
  "FilterDropdownButton.tsx",
  "EvaluationLensHeaderButton.tsx",
  "GmStanceHeaderButton.tsx",
  "SimGameHeader.tsx",
  "CompactModule.tsx",
  "Collapsible.tsx",
  "PlayerCardKit.tsx",
  "PickGroupList.tsx",
  // app: settings / menu list screens, where a chevron-per-line IS the list convention (not stat rows or player rows)
  "MoreScreen.tsx",
  "FeaturesScreen.tsx",
  "PaywallScreen.tsx",
  "RootNavigator.tsx",
  "GmOrb.tsx",
  "AlertsScreen.tsx",
  // web: carousel pager arrow (not a row)
  "StoryCarousel.tsx",
  // app: screen-level files NOT yet audited line by line (some are expand toggles such as MyTeamScreen analysis rows, some
  // are section "see all" links, some may be redundant row chevrons). Follow-up: audit each, then drop it from this list.
  "MyTeamScreen.tsx",
  "HomeScreen.tsx",
  "RecapScreen.tsx",
  "GmPlanScreen.tsx",
  "DraftCenterScreen.tsx",
  "PlayerDetailScreen.tsx",
  "PlayerCompareScreen.tsx",
  "PlayerHero.tsx",
  "AwardsStrip.tsx",
  "DashboardBlocks.tsx",
  "RecapReadyCard.tsx",
  "StorylineSummaryCard.tsx",
  "DashboardGuessCard.tsx",
  "SimGameDraft.tsx",
]);
// Shared row/tile components that MUST stay chevron-free (the rule lives in them).
const MUST_BE_CLEAN = ["MetricCard.tsx", "InsightRow.tsx", "PlayerInsightRow.tsx", "LeagueStandingStrips.tsx", "LeaguePulseCard.tsx", "PlayerIdentityRow.tsx", "DraftPickAssetRow.tsx", "StructuredRow.tsx", "InsightLink.tsx", "PlayerRow.tsx"];

function walk(dir: string, out: string[] = []): string[] {
  for (const e of readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, e.name);
    if (e.isDirectory()) { if (e.name !== "node_modules") walk(full, out); } else if (/\.tsx$/.test(e.name) && !/\.test\./.test(e.name)) out.push(full);
  }
  return out;
}
const NAV_CHEVRON = /chevron-forward|ui-insight-chevron|>\s*›\s*<|styles\.chevron\}>›|<Chevron\s*\/>/;

describe("no redundant chevron on a fully tappable row", () => {
  const roots = [path.resolve(__dirname, ".."), path.resolve(__dirname, "../../../mobile/src")];
  const files = roots.flatMap((r) => walk(r));
  it("shared row / tile components draw no navigation chevron", () => {
    const bad = files.filter((f) => MUST_BE_CLEAN.includes(path.basename(f)) && NAV_CHEVRON.test(readFileSync(f, "utf8"))).map((f) => path.basename(f));
    expect(bad).toEqual([]);
  });
  it("no other file introduces a navigation chevron without an allowlist reason", () => {
    const bad = files
      .filter((f) => !ALLOWED_NAV_CHEVRON.has(path.basename(f)) && NAV_CHEVRON.test(readFileSync(f, "utf8")))
      .map((f) => path.relative(path.resolve(__dirname, "../../.."), f));
    expect(bad).toEqual([]);
  });
});
