#!/usr/bin/env node
// Guard for selection mode (smart footer upgrade, docs/ui-patterns.md "Smart footer rules"). A pick-from-a-list + submit
// screen carries its submit in the footer, never in a second sticky bar:
//   web:    selectionPrimary(...) from lib/bottomNav.ts handed to the page's tab bar `primary` (the footer pill's primary chip)
//   mobile: <SelectionActionBar .../> (site-shell screens: sits below the list, clear of the orb) or, inside the Fantasy Sim,
//           the pill's primary via selectionPrimary.
// This fails CI when a screen keeps a multi-selection state (selectedIds / selectedPickIds / selectionCount) next to a submit
// handler (search / analyze / submit / evaluate) without using either, or when it hand-rolls a sticky bottom CTA next to a
// selection (`ctaBar`, "position: sticky; bottom").
//
// Audit 2026-11-17 (every select-and-submit list): Trade Finder and Trade Analyzer (web + app) use it. Player Compare picks two
// slots through a sheet (no list selection); the Sim draft and waivers act per row; roster moves and the watchlist have no bulk
// selection today; LiveDraftTradeEvaluator is an in-panel evaluator. If one of those gains a multi-select, it must adopt this.
//
// Usage: node scripts/check_selection_submit.mjs   (exit 1 on any violation)
import { readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const TREES = ["web-next/src", "mobile/src"];
const SELECTION_STATE = /\b(selectedIds|selectedPickIds|selectedPlayerIds|selectedKeys|selectionCount)\b/;
const SUBMIT = /\b(search|analyze|submit|evaluate|runSearch)\s*(\(|=)/;
const USES = /\bselectionPrimary\s*\(|<SelectionActionBar\b/;
const HAND_ROLLED = /\bctaBar\b|sticky\s+bottom|position:\s*["']?sticky["']?[^\n]*bottom/;
const SKIP = /\.test\.|SelectionActionBar\.tsx$|bottomNav\.ts$|check_selection_submit/;

function* walk(dir) {
  for (const name of readdirSync(dir)) {
    if (name === "node_modules" || name.startsWith(".")) continue;
    const full = path.join(dir, name);
    if (statSync(full).isDirectory()) yield* walk(full);
    else if (/\.tsx?$/.test(name)) yield full;
  }
}

export function scan() {
  const problems = [];
  for (const tree of TREES) {
    for (const file of walk(path.join(ROOT, tree))) {
      const rel = path.relative(ROOT, file);
      if (SKIP.test(rel)) continue;
      const src = readFileSync(file, "utf8");
      if (!SELECTION_STATE.test(src)) continue;
      if (HAND_ROLLED.test(src)) problems.push(`${rel}: hand-rolled sticky bottom bar next to a selection (use selectionPrimary / SelectionActionBar)`);
      if (SUBMIT.test(src) && !USES.test(src)) problems.push(`${rel}: selection + submit without selection mode (use selectionPrimary on web, <SelectionActionBar> in the app)`);
    }
  }
  return problems;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const problems = scan();
  if (problems.length) {
    console.error(problems.join("\n"));
    process.exit(1);
  }
  console.log("selection submit guard: ok");
}
