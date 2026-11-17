#!/usr/bin/env node
// Guard for the header rewrite (docs/audits/2026-11-header-rewrite.md, phase 7): the legacy headers are retired.
//   web:    components/Header.tsx (the old wrapping row + dropdown pickers) is now components/AppHeader.tsx (ShellHeader on phones, one
//           bar elsewhere, both on the shared LeagueIdentity + LeagueSwitcherSheet). Nothing may import "@/components/Header" / "./Header",
//           and no LeagueSwitcherButton / LeagueLensPicker / EvaluationLensButton may come back.
//   mobile: the in-content BrandHeaderBar (a second header stacked under the native one) is gone; a screen's title goes through
//           useScreenHeaderTitle and its actions through its own native `headerRight`.
// Fails CI when a legacy header file exists or is imported/rendered anywhere in web-next/src or mobile/src.
//
// Usage: node scripts/check_legacy_header.mjs   (exit 1 on any violation)
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const TREES = ["web-next/src", "mobile/src"];
const LEGACY_FILES = ["web-next/src/components/Header.tsx", "mobile/src/components/BrandHeaderBar.tsx"];
const LEGACY_USE = [
  [/from\s+["'](?:@\/components\/Header|\.{1,2}\/(?:components\/)?Header)["']/, 'imports the legacy "Header" component'],
  [/from\s+["'][^"']*\/BrandHeaderBar["']|<BrandHeaderBar\b/, "uses the retired BrandHeaderBar"],
  [/\b(LeagueSwitcherButton|LeagueLensPicker|EvaluationLensButton)\b/, "uses a retired header dropdown picker"],
];
const SKIP = /check_legacy_header|\.test\./;

function* walk(dir) {
  for (const name of readdirSync(dir)) {
    if (name === "node_modules" || name.startsWith(".")) continue;
    const full = path.join(dir, name);
    if (statSync(full).isDirectory()) yield* walk(full);
    else if (/\.(tsx?|mjs)$/.test(name)) yield full;
  }
}

const problems = [];
for (const f of LEGACY_FILES) if (existsSync(path.join(ROOT, f))) problems.push(`${f} still exists (retired; use AppHeader / useScreenHeaderTitle)`);
for (const tree of TREES) {
  for (const file of walk(path.join(ROOT, tree))) {
    if (SKIP.test(file)) continue;
    const text = readFileSync(file, "utf8");
    for (const [re, why] of LEGACY_USE) {
      // Comments may name a retired component; only real code counts.
      const code = text.replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|[^:])\/\/[^\n]*/g, "$1");
      if (re.test(code)) problems.push(`${path.relative(ROOT, file)}: ${why}`);
    }
  }
}

if (problems.length) {
  console.error("Legacy header check failed:\n" + problems.map((p) => `  - ${p}`).join("\n"));
  process.exit(1);
}
console.log("Legacy header check passed (no Header.tsx / BrandHeaderBar imports).");
