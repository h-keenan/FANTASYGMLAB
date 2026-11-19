#!/usr/bin/env node
/**
 * Loading identity guard (docs/ui-patterns.md, "Loading identity"). Every loading state is a content-shaped skeleton
 * from the ONE shared set (web-next/src/components/Skeleton.tsx, mobile/src/components/Skeleton.tsx). This scan fails on:
 *   1. visible "Loading..." / "Checking..." style text (JSX text or a string literal ending in an ellipsis) outside the skeleton module;
 *      screen-reader-only names (aria-label, accessibilityLabel, `sr-only`, `name:` in tests) are fine.
 *   2. a mobile screen drawing a bare `ActivityIndicator` outside the allowlist (inline action busy states: a button, a
 *      row's trailing control, a progress line next to real text). A whole screen or region that is loading uses a skeleton.
 *   3. the retired `BrandedSpinner` or a `<LoadingScreen status=...>` text prop.
 * Run by `npm test` in web-next (src/lib/skeletonIdentity.test.ts) and mobile (src/lib/skeletonIdentity.test.ts).
 * Exports `scan()` for the tests; run directly: `node scripts/check_skeleton_identity.mjs`.
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

/** Files allowed to carry loading words or a spinner, each with the reason. Keep this list short; it should only shrink. */
export const ALLOW = [
  { file: "web-next/src/components/SimGameContent.tsx", why: "native <option> text cannot hold a skeleton (league / team pickers)" },
  { file: "web-next/src/components/PlayerNewsTab.tsx", why: "'Load more' button busy label" },
  { file: "mobile/src/components/PlayerNewsSection.tsx", why: "'Load more' button busy label" },
  { file: "web-next/src/components/EspnImportForm.tsx", why: "import button busy label" },
  { file: "web-next/src/components/SleeperUsernameRelink.tsx", why: "save button busy label" },
  { file: "web-next/src/lib/dashboardLayout.ts", why: "pill/status string for the trade-ideas chip" },
  { file: "web-next/src/components/TradeFinderContent.tsx", why: "'Find Realistic Trades' button busy label" },
  { file: "mobile/src/screens/TradeFinderScreen.tsx", why: "search action busy title" },
  { file: "mobile/src/lib/dashboardLayout.ts", why: "pill/status string for the trade-ideas chip (twin of web)" },
];
const SPINNER_ALLOW = [
  { file: "mobile/src/components/Button.tsx", why: "button busy state" },
  { file: "mobile/src/components/EspnLoginPanel.tsx", why: "button busy state" },
  { file: "mobile/src/components/EspnLeagueImport.tsx", why: "button busy state" },
  { file: "mobile/src/components/GuessThePlayerPrompt.tsx", why: "submit busy state under real content" },
  { file: "mobile/src/components/GuessThePlayerNameMatchPrompt.tsx", why: "submit busy state under real content" },
  { file: "mobile/src/components/TradeOutcomePrompt.tsx", why: "answer busy state under real content" },
  { file: "mobile/src/screens/MoreScreen.tsx", why: "row trailing busy control" },
  { file: "mobile/src/screens/GmPlanScreen.tsx", why: "row trailing busy control" },
  { file: "mobile/src/screens/LoginScreen.tsx", why: "sign-in button busy state" },
  { file: "mobile/src/screens/GmGameScreen.tsx", why: "Sim To progress line beside its status text" },
];

const EXT = /\.(tsx?|jsx?)$/;
const SKIP_DIR = /(node_modules|\.next|\.expo|dist|build|coverage)$/;
const isTest = (f) => /\.test\.(tsx?|mjs|js)$/.test(f) || f.endsWith(".stories.tsx");

function walk(dir, out = []) {
  for (const name of fs.readdirSync(dir)) {
    const full = path.join(dir, name);
    const st = fs.statSync(full);
    if (st.isDirectory()) {
      if (!SKIP_DIR.test(name)) walk(full, out);
    } else if (EXT.test(name) && !isTest(name)) out.push(full);
  }
  return out;
}

// Visible loading copy: a string/JSX text that starts with a progress verb and ends in an ellipsis.
const LOADING_TEXT = /(?:^\s*|[>"'`{(]\s*)(?:Loading|Checking|Fetching|Searching|Reading|Building|Running)\b[^<"'`\n]*?(?:…|\.\.\.|&hellip;)/;
const SR_ONLY = /(aria-label|accessibilityLabel|sr-only|aria-live|role="status"|\/\/|^\s*\*|^\s*\/\*)/;

export function scan() {
  const problems = [];
  const allowed = new Set(ALLOW.map((a) => a.file));
  const spinnerOk = new Set(SPINNER_ALLOW.map((a) => a.file));
  const usedAllow = new Set();
  const usedSpinner = new Set();
  for (const tree of ["web-next/src", "mobile/src"]) {
    for (const abs of walk(path.join(root, tree))) {
      const rel = path.relative(root, abs).split(path.sep).join("/");
      const lines = fs.readFileSync(abs, "utf8").split("\n");
      lines.forEach((line, i) => {
        const where = `${rel}:${i + 1}`;
        if (LOADING_TEXT.test(line) && !SR_ONLY.test(line)) {
          if (allowed.has(rel)) usedAllow.add(rel);
          else problems.push(`${where}  bare loading text: use a skeleton from the shared Skeleton module  -> ${line.trim().slice(0, 90)}`);
        }
        if (/BrandedSpinner/.test(line) && !/^\s*(\/\/|\*|\/\*)/.test(line)) problems.push(`${where}  BrandedSpinner is retired: use SkeletonPage / SkeletonList`);
        if (/<LoadingScreen[^>]*\bstatus=/.test(line)) problems.push(`${where}  LoadingScreen takes label/layout/family, not status text`);
        if (rel.startsWith("mobile/") && /<ActivityIndicator\b/.test(line)) {
          if (spinnerOk.has(rel)) usedSpinner.add(rel);
          else if (allowed.has(rel)) usedAllow.add(rel);
          else problems.push(`${where}  bare ActivityIndicator: a loading screen or region uses a skeleton (inline busy states go in SPINNER_ALLOW with a reason)`);
        }
      });
    }
  }
  // An allowlist entry that no longer excuses anything is dead weight that would silently excuse a future regression.
  for (const a of ALLOW) if (!usedAllow.has(a.file)) problems.push(`${a.file}  ALLOW entry no longer needed (no bare loading text or spinner in it); remove it`);
  for (const a of SPINNER_ALLOW) if (!usedSpinner.has(a.file)) problems.push(`${a.file}  SPINNER_ALLOW entry no longer needed (no ActivityIndicator in it); remove it`);
  return problems;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const problems = scan();
  if (problems.length) {
    console.error(`Loading identity check failed (${problems.length}):\n` + problems.join("\n"));
    process.exit(1);
  }
  console.log("Loading identity check passed.");
}
