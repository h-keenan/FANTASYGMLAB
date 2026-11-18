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
//   4. a value delta (gain / balance / edge / net value / margin) coloured danger or tone "danger" (a negative delta is muted);
//   5. a card accent stripe chosen with a ternary that can turn red;
//   6b. a Give / "You give" label coloured danger (Give is neutral grey);
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
// A value DELTA (trade gain / balance / edge / net value / margin) is not a verdict: a negative one is muted with an arrow
// ("You give up 747"), never red. The 2026-11 GM Plan "-747" in red slipped past rules 1-3 because that line said "gain" and
// tone "danger" (a compact-tone string literal, not a var(--color-*) token) and never used a verdict / odds word.
const DELTA_WORDS = /\b(gain|gainColor|balanceColor|tradeGain|trade_gain|netValue|net_value|netPts|netPoints|net_points\w*|pointsDelta)\b/i;
// Trade History (2026-11-17) slipped through because its red lived on a tone ternary (netPts < 0 ? "danger") with the delta
// named netPts (not in DELTA_WORDS) and its stripe came from a mapped helper (verdictToneColorVar). Two general rules:
//   6. a negative-sign ternary that yields danger (x < 0 ? "danger", delta < 0 ? colors.danger): a loss is muted;
//   7. an accent stripe fed by a verdict helper (accent = verdictColor(...)): one calm stripe, the verdict lives on a chip.
// Rule 6 covers the trade / track-record surfaces (other surfaces, e.g. live scoring, have their own meaning for a negative).
const TRADE_FILE = /(Trade|TrackRecord|trackRecord)/;
const NEGATIVE_DANGER = /<\s*0\s*\?\s*(["']danger["']|var\(--color-danger\)|colors\.danger)/;
const STRIPE_VERDICT = /\baccent\s*[=:]\s*\{?[^;]*\bverdict\w*(ColorVar|Color|Tone)\w*\s*\(/i;
const DANGER_TONE = /(["'])danger\1|var\(--color-danger\)|\bcolors\.danger\b/;
// A card / module accent stripe chosen with a ternary that can turn it red (accent = x ? danger : accent): one calm stripe;
// the reason (an injury) is said in the text or a small chip.
const STRIPE_DANGER = /\baccent\s*=\s*\{?[^;]*injur[^;]*\?[^;]*(var\(--color-danger\)|colors\.danger|["']danger["'])/i;

// A "Give" / "You give" label is neutral grey ("Get" may stay green): giving a player is not a loss verdict, so it is never red.
const GIVE_LABEL = />\s*(You give|Give)\s*<|["'`]You give["'`]|\bside\s*===?\s*["']give["']\s*\?\s*(["']danger["']|var\(--color-danger\)|colors\.danger)/;

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
    if (GIVE_LABEL.test(line) && DANGER_TONE.test(line)) {
      problems.push(`${rel}:${i + 1}: a Give / "You give" label is coloured red (${line.trim().slice(0, 80)}); Give is neutral grey, only Get may be green`);
      return;
    }
    if (STRIPE_DANGER.test(line)) {
      problems.push(`${rel}:${i + 1}: card accent stripe can turn red (${line.trim().slice(0, 80)}); one calm stripe, say the reason in text or a chip`);
      return;
    }
    if (TRADE_FILE.test(rel) && NEGATIVE_DANGER.test(line)) {
      problems.push(`${rel}:${i + 1}: a negative value is coloured red (${line.trim().slice(0, 80)}); a loss is muted ("Down 12" chip), never red`);
      return;
    }
    if (STRIPE_VERDICT.test(line)) {
      problems.push(`${rel}:${i + 1}: accent stripe fed by a verdict colour (${line.trim().slice(0, 80)}); one calm stripe, put the verdict on a chip`);
      return;
    }
    if (DELTA_WORDS.test(line) && DANGER_TONE.test(line) && !/deltaBand|bandCompactTone/.test(line)) {
      problems.push(`${rel}:${i + 1}: a value delta is coloured red (${line.trim().slice(0, 80)}); use deltaBand (green up, muted down) from verdictTone.ts`);
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
