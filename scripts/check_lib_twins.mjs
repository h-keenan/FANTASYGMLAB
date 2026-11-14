#!/usr/bin/env node
// Drift guard for the web/mobile lib twins.
//
// web-next/src/lib and mobile/src/lib each hold hand-maintained copies of the
// same pure-TS modules (feature catalog, verdict copy, trade bands, ...).
// There is no shared package, so nothing stops one copy being edited alone.
// This check classifies EVERY same-named non-test file pair and fails when:
//
//   - a pair carrying `// SHARED BEGIN` / `// SHARED END` markers in both
//     files has different code between the markers (comments/imports/quote
//     style/whitespace ignored). This is automatic, no registry entry;
//   - a pair listed in IDENTICAL is not byte-identical;
//   - a pair listed in MIRRORED differs in code (comments, import lines,
//     quote style, whitespace and trailing commas ignored);
//   - a pair is not classified at all (a new twin must pick a bucket, so
//     drift can never start silently);
//   - a pair listed in DIVERGED has actually converged (promote it) or a
//     registry entry points at a file that no longer exists in both trees.
//
// DIVERGED is the acknowledged-debt baseline: twins that already differ in
// code (platform imports, extra helpers, real drift). Shrink it by promoting
// files to MIRRORED/SHARED, never grow it to silence a failure.
//
// Usage: node scripts/check_lib_twins.mjs   (exit 1 on any violation)
import { readdirSync, readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

// Byte-identical in both trees (generated files and imports-free pure modules).
export const IDENTICAL = [
  "compactModule.ts",
  "moduleTemplates.ts",
  "teamStatusModules.ts",
  "chartSeries.ts",
  "simSummaries.ts",
  "simTradeSheet.ts",
  "simSetupView.ts",
  "tradeSheetPicker.ts",
  "confirmInPlace.ts",
  "overlayStack.ts",
  "busyRetry.ts",
  "destinationAccents.generated.ts",
  "directionCheckin.ts",
  "draftSignals.ts",
  "filterSheet.ts",
  "freeLimits.ts",
  "injuryTone.generated.ts",
  "limitWall.ts",
  "lineupSlots.ts",
  "liveFeed.ts",
  "liveScores.ts",
  "matchupPlanner.ts",
  "multiTeamIdeas.ts",
  "multiTeamTrade.ts",
  "insightLinks.ts",
  "navCatalog.ts",
  "opponentProfile.ts",
  "pageFamilies.ts",
  "playerCard.ts",
  "playerListRow.ts",
  "playerNameDisplay.ts",
  "pqvContext.ts",
  "sampleLeague.ts",
  "sessionTab.ts",
  "sheetTabs.ts",
  "simAsOf.ts",
  "simCrest.ts",
  "simGame.ts",
  "simHistory.ts",
  "simPlayerSheet.ts",
  "simLeagueRosters.ts",
  "simScouting.ts",
  "simTo.ts",
  "weeklyProjection.ts",
  "simReview.ts",
  "simDraft.ts",
  "simGameFlow.ts",
  "simScroll.ts",
  "simRecapStory.ts",
  "storyCarousel.ts",
  "motion.ts",
  "simNotifications.ts",
  "simLayout.ts",
  "simPresentation.ts",
  "startHere.ts",
  "startSitRange.ts",
  "tabIcons.ts",
  "teamInitials.ts",
  "terms.ts",
  "tradeCautions.ts",
  "tradeValueBands.generated.ts",
  "verdictText.ts",
];

// Same code, differing only in comments / import specifiers / quote style.
export const MIRRORED = [
  "bottomNav.ts",
  "bottomBarMetrics.ts",
  "dropsPresentation.ts",
  "experienceCopy.ts",
  "formatPlayerName.ts",
  "notificationControls.ts",
  "freeLeagueCap.ts",
  "glossary.ts",
  "paidPreviews.ts",
  "playerNameFixtures.ts",
  "paywallCopy.ts",
  "firstRunFlow.ts",
  "premiumComparison.ts",
  "sleeperConnectErrors.ts",
  "support.ts",
  "tapForWhyContent.ts",
  "teamStatus.ts",
  "useDelayedFlag.ts",
  "useSimLeagueRosters.ts",
  "valueHistoryPresentation.ts",
];

// Known, already-divergent twins (see header). Keep sorted.
export const DIVERGED = [
  // Platform glue that is meant to differ (storage, SDKs, env, gestures).
  "analytics.ts",
  "useOverlay.ts", // platform hook over the shared overlayStack (web: useId + runtime; mobile: Modal registration)
  "api.ts", // types are hand-duplicated; see docs/web-mobile-lib-twins.md
  "env.ts",
  "errorReporter.ts",
  "guessThePlayerDismissed.ts",
  "guessThePlayerNameMatchDismissed.ts",
  "onboardingAnalytics.ts",
  "sheetGesture.ts",
  "useMotion.ts", // platform glue: matchMedia / IntersectionObserver vs AccessibilityInfo
  "simRookieNotice.ts",
  "supabase.ts",
  // Pure logic that has drifted or been edited on one side only. Promote to
  // MIRRORED / SHARED markers as each one is reconciled.
  "alertReadSync.ts",
  "destinationAccent.ts",
  "featureCatalog.ts",
  "gamesPresentation.ts",
  "gmPlanSnapshot.ts",
  "guillotine.ts",
  "idpPresentation.ts",
  "leaguePlatform.ts",
  "leaguePlayerSearch.ts",
  "managerTendencies.ts",
  "matchupPresentation.ts",
  "myTeamAnalysis.ts",
  "percentileExplorer.ts",
  "pickGroups.ts",
  "playerQuickViewPresentation.ts",
  "playerTier.ts",
  "portfolioLoader.ts",
  "portfolioProgress.ts",
  "roundupPresentation.ts",
  "sampleDashboard.ts",
  "scoutingLens.ts",
  "thisWeek.ts",
  "todayPlan.ts",
  "tradeOffer.ts",
  "tradeShortcuts.ts",
];

const SHARED_BEGIN = "// SHARED BEGIN";
const SHARED_END = "// SHARED END";

export function normalizeCode(source) {
  return source
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/^\s*\/\/.*$/gm, "")
    .replace(/^\s*import\b[\s\S]*?from\s+["'][^"']+["'];?\s*$/gm, "")
    .replace(/^\s*import\s+["'][^"']+["'];?\s*$/gm, "")
    .replace(/\\'/g, "'")
    .replace(/'/g, '"')
    .replace(/\s+/g, "")
    .replace(/;/g, "")
    .replace(/,(?=[)\]}])/g, "");
}

function sharedBlock(source) {
  const start = source.indexOf(SHARED_BEGIN);
  const end = source.indexOf(SHARED_END);
  if (start < 0 || end <= start) return null;
  return source.slice(start + SHARED_BEGIN.length, end);
}

function listLib(dir) {
  return new Set(readdirSync(dir).filter((f) => f.endsWith(".ts") && !/\.test\.ts$/.test(f)));
}

export function checkTwins(root) {
  const webDir = path.join(root, "web-next/src/lib");
  const mobileDir = path.join(root, "mobile/src/lib");
  const web = listLib(webDir);
  const mobile = listLib(mobileDir);
  const twins = [...web].filter((f) => mobile.has(f)).sort();
  const errors = [];
  const registered = new Set([...IDENTICAL, ...MIRRORED, ...DIVERGED]);

  for (const name of registered) {
    if (!twins.includes(name)) {
      errors.push(`${name}: listed in the twin registry but missing from web-next/src/lib or mobile/src/lib`);
    }
  }

  for (const name of twins) {
    const w = readFileSync(path.join(webDir, name), "utf8");
    const m = readFileSync(path.join(mobileDir, name), "utf8");
    const wShared = sharedBlock(w);
    const mShared = sharedBlock(m);
    if ((wShared === null) !== (mShared === null)) {
      errors.push(`${name}: SHARED markers exist in only one of the two copies`);
      continue;
    }
    if (wShared !== null) {
      if (normalizeCode(wShared) !== normalizeCode(mShared)) {
        errors.push(`${name}: SHARED block differs between web-next and mobile; edit both together`);
      }
      continue;
    }
    if (IDENTICAL.includes(name)) {
      if (w !== m) errors.push(`${name}: must be byte-identical in web-next and mobile`);
    } else if (MIRRORED.includes(name)) {
      if (normalizeCode(w) !== normalizeCode(m)) {
        errors.push(`${name}: code drifted between web-next and mobile (only comments/imports/quotes may differ)`);
      }
    } else if (DIVERGED.includes(name)) {
      if (normalizeCode(w) === normalizeCode(m)) {
        errors.push(`${name}: the two copies now match; move it from DIVERGED to MIRRORED (or IDENTICAL)`);
      }
    } else {
      errors.push(
        `${name}: new web/mobile lib twin with no drift classification; add it to IDENTICAL, MIRRORED or DIVERGED in scripts/check_lib_twins.mjs (or add SHARED markers)`,
      );
    }
  }
  return { errors, twins };
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
  const { errors, twins } = checkTwins(root);
  if (errors.length) {
    console.error(`Lib twin drift check failed (${errors.length}):`);
    for (const e of errors) console.error(`  - ${e}`);
    process.exit(1);
  }
  console.log(`Lib twin drift check passed (${twins.length} twin files).`);
}
