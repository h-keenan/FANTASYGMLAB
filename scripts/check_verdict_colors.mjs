#!/usr/bin/env node
// Guard for the shared verdict colour standard (UI audit batch C, docs/ui-patterns.md "Verdict colours").
// Every win %, odds figure and verdict is coloured by the ONE map in lib/verdictTone.ts (via verdictToneCss.ts on web,
// verdictToneTheme.ts in the app). A verdict sentence is neutral text; semantic colour is only on small chips. This
// fails CI when a line that talks about a win chance, odds, probability or verdict hard-codes a semantic or red colour:
//
//   1. a semantic token (var(--color-danger|success|warning), colors.danger|success|successBright|warning) on the same
//      line as winPercent / winChance / odds / probability / verdict / favored words;
//   2. a raw red hex (#ef4444, #dc2626, #f87171, #b91c1c, ...) on such a line;
//   3. an inline win-percent threshold ladder (winPercent >= 55 ? "success" ...) instead of percentBand;
//
// A line that already goes through the map (probabilityBand, percentBand, verdictBand, bandColor, bandColorVar,
// probabilityColor*, percentColor*, verdictColor*, bandSimTone, bandCompactTone) is fine. Use `// verdict-color-ok: reason`
// on the line (or the line above) only for a real non-verdict meaning that merely mentions one of the words.
//
// Usage: node scripts/check_verdict_colors.mjs   (exit 1 on any violation)
import { readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const TREES = ["web-next/src", "mobile/src"];
const SKIP_FILE = /(verdictTone(Css|Theme)?\.ts|check_verdict_colors|verdictColors?\.test|\.test\.|theme\.ts|globals\.css|design_tokens|\.generated\.)/;

const WORDS = /\b(win(?:Pct|Percent|Prob\w*|Chance)|odds|probab\w*|verdict\w*|favou?red|onTrack|title_probability|playoff_probability)\b|win_prob|winprob/i;
const SEMANTIC = /var\(--color-(danger|success|warning)\)|\bcolors\.(danger|success|successBright|warning)\b/;
const RED_HEX = /#(ef4444|dc2626|f87171|b91c1c|ff3b30|e11d48|f43f5e|ff4d4f)\b/i;
const LADDER = /(winPercent|winPct|\bpct|\bwp|probability)\s*(>=|<=|>|<)\s*[\d.]+\s*\?\s*["'](success|danger|warning)["']/;
const MAPPED = /(probabilityBand|percentBand|verdictBand|deltaBand|bandColor|bandColorVar|probabilityColor|percentColor|verdictColor|probabilityColorVar|percentColorVar|verdictColorVar|bandSimTone|bandCompactTone)/;
const OK = /verdict-color-ok/;

function* walk(dir) {
  for (const name of readdirSync(dir)) {
    if (name === "node_modules" || name.startsWith(".")) continue;
    const full = path.join(dir, name);
    if (statSync(full).isDirectory()) yield* walk(full);
    else if (/\.(tsx?|css)$/.test(name)) yield full;
  }
}

export function scanText(rel, text) {
  const problems = [];
  const lines = text.split("\n");
  lines.forEach((line, i) => {
    if (/^\s*(\/\/|\*|\/\*)/.test(line)) return;
    if (OK.test(line) || (i > 0 && OK.test(lines[i - 1]))) return;
    if (LADDER.test(line)) {
      problems.push(`${rel}:${i + 1}: inline probability threshold ladder; use percentBand / probabilityBand from verdictTone.ts`);
      return;
    }
    if (MAPPED.test(line)) return;
    if (WORDS.test(line) && RED_HEX.test(line)) {
      problems.push(`${rel}:${i + 1}: hard-coded red on a verdict / probability line (${line.trim().slice(0, 80)}); use the shared verdict map`);
    } else if (WORDS.test(line) && SEMANTIC.test(line)) {
      problems.push(`${rel}:${i + 1}: hard-coded semantic colour on a verdict / probability line (${line.trim().slice(0, 80)}); use the shared verdict map`);
    }
  });
  return problems;
}

export function scan() {
  const problems = [];
  for (const tree of TREES) {
    for (const file of walk(path.join(ROOT, tree))) {
      const rel = path.relative(ROOT, file);
      if (SKIP_FILE.test(rel)) continue;
      problems.push(...scanText(rel, readFileSync(file, "utf8")));
    }
  }
  return problems;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const problems = scan();
  if (problems.length) {
    console.error(`Verdict colour check failed (${problems.length}):`);
    for (const p of problems) console.error(`  - ${p}`);
    process.exit(1);
  }
  console.log("Verdict colour check passed.");
}
