#!/usr/bin/env node
/**
 * Navigation-sheet guard. "Where to go" (Search / GM orb) and "More" used to be two separately built lists of the same
 * destinations and drifted apart (owner, 2026-11-17: "the search menu looks different than the More menu"). There is now ONE
 * registry (lib/navCatalog.ts + lib/navSheet.ts, byte-identical twins) and ONE sheet per platform
 * (web-next/src/components/NavSheet.tsx; the app's GM orb sheet, mobile/src/components/GmOrb.tsx).
 *
 * Fails when destination lists are built or rendered anywhere else:
 *   1. web: `useNavDestinations(` (the hook every destination list is built from) outside NavSheet and the desktop sidebar.
 *   2. web: `navSheetGroups(` outside NavSheet; app: outside GmOrb.
 *   3. app: `navPagesIn(` / `NAV_PAGES` outside GmOrb and the lib files that adapt the catalog (orbTabs, navCatalog).
 *   4. either: the retired parallel More menu (`moreLeagueGroups`, `shell-more-menu`, a `"More"` Sheet title).
 * Comments are ignored. Run by CI (.github/workflows/ci.yml) and web `npm test` (src/lib/navSheetScan.test.ts).
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

/** Files allowed to build or render a destination list, each with the reason. */
const WEB_HOOK_OK = new Map([
  ["web-next/src/components/NavSheet.tsx", "the shared sheet"],
  ["web-next/src/components/DesktopSidebar.tsx", "the desktop rail: same registry, always-visible form of the same list"],
  ["web-next/src/lib/navDestinations.ts", "defines the hook"],
]);
const WEB_GROUPS_OK = new Set(["web-next/src/components/NavSheet.tsx", "web-next/src/lib/navSheet.ts"]);
const APP_GROUPS_OK = new Set(["mobile/src/components/GmOrb.tsx", "mobile/src/lib/navSheet.ts"]);
const APP_CATALOG_OK = new Set(["mobile/src/components/GmOrb.tsx", "mobile/src/lib/orbTabs.ts", "mobile/src/lib/navCatalog.ts"]);

const EXT = /\.(tsx?)$/;
const SKIP_DIR = /^(node_modules|\.next|\.expo|dist|build|coverage|\..*)$/;

function walk(dir, out = []) {
  if (!fs.existsSync(dir)) return out;
  for (const name of fs.readdirSync(dir)) {
    const full = path.join(dir, name);
    if (fs.statSync(full).isDirectory()) {
      if (!SKIP_DIR.test(name)) walk(full, out);
    } else if (EXT.test(name) && !/\.test\./.test(name)) out.push(full);
  }
  return out;
}

const stripComments = (text) => text.replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|[^:])\/\/[^\n]*/g, "$1");

export function scan() {
  const problems = [];
  const rel = (f) => path.relative(root, f).split(path.sep).join("/");
  // An allowlisted file that no longer matches the pattern it is excused for is dead weight (it would silently excuse a
  // future regression), so every entry must be exercised: the lists only shrink.
  const used = { hook: new Set(), webGroups: new Set(), appGroups: new Set(), appCatalog: new Set() };
  for (const file of walk(path.join(root, "web-next/src"))) {
    const r = rel(file);
    const code = stripComments(fs.readFileSync(file, "utf8"));
    if (/\buseNavDestinations\s*\(/.test(code) && WEB_HOOK_OK.has(r)) used.hook.add(r);
    if (/\bnavSheetGroups\s*[<(]/.test(code) && WEB_GROUPS_OK.has(r)) used.webGroups.add(r);
    if (/\buseNavDestinations\s*\(/.test(code) && !WEB_HOOK_OK.has(r)) problems.push(`${r}: builds a destination list with useNavDestinations; open the shared NavSheet instead`);
    if (/\bnavSheetGroups\s*[<(]/.test(code) && !WEB_GROUPS_OK.has(r)) problems.push(`${r}: groups destinations outside components/NavSheet.tsx`);
    if (/moreLeagueGroups|shell-more-menu/.test(code)) problems.push(`${r}: the retired separate More menu (use components/NavSheet.tsx)`);
  }
  for (const file of walk(path.join(root, "mobile/src"))) {
    const r = rel(file);
    const code = stripComments(fs.readFileSync(file, "utf8"));
    if (/\bnavSheetGroups\s*[<(]/.test(code) && APP_GROUPS_OK.has(r)) used.appGroups.add(r);
    if (/\b(navPagesIn\s*\(|NAV_PAGES\b)/.test(code) && APP_CATALOG_OK.has(r)) used.appCatalog.add(r);
    if (/\bnavSheetGroups\s*[<(]/.test(code) && !APP_GROUPS_OK.has(r)) problems.push(`${r}: groups destinations outside the GM orb sheet (GmOrb.tsx)`);
    if (/\b(navPagesIn\s*\(|NAV_PAGES\b)/.test(code) && !APP_CATALOG_OK.has(r)) problems.push(`${r}: lists catalog pages outside the GM orb sheet`);
    if (/moreLeagueGroups|leagueMoreGroups/.test(code)) problems.push(`${r}: the retired separate More grouping (use lib/navSheet.ts)`);
  }
  for (const f of WEB_HOOK_OK.keys()) if (!used.hook.has(f)) problems.push(`${f}: WEB_HOOK_OK entry no longer uses useNavDestinations (remove it)`);
  for (const f of WEB_GROUPS_OK) if (!used.webGroups.has(f)) problems.push(`${f}: WEB_GROUPS_OK entry no longer calls navSheetGroups (remove it)`);
  for (const f of APP_GROUPS_OK) if (!used.appGroups.has(f)) problems.push(`${f}: APP_GROUPS_OK entry no longer calls navSheetGroups (remove it)`);
  for (const f of APP_CATALOG_OK) if (!used.appCatalog.has(f)) problems.push(`${f}: APP_CATALOG_OK entry no longer lists catalog pages (remove it)`);
  return problems;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const problems = scan();
  if (problems.length) {
    console.error("Navigation sheet check failed:\n" + problems.map((p) => `  - ${p}`).join("\n"));
    process.exit(1);
  }
  console.log("Navigation sheet check passed (one registry, one sheet per platform).");
}
