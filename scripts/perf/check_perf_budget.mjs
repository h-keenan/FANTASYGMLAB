// Lightweight perf guard (CI friendly, no browser): run after `next build` in web-next/.
//   node scripts/perf/check_perf_budget.mjs            -> exits 1 on a violation
// 1. First-load JS per route stays under web-next/perf-budget.json (KB, uncompressed).
// 2. CSS never animates a property that repaints/re-layouts every frame (background-position, top/left/width/height,
//    box-shadow, filter, backdrop-filter): animate transform/opacity so the compositor does the work. Existing legacy
//    keyframes are allowlisted by name; do not add to the list, convert instead (see docs/perf-budget.md).
import fs from "fs";
import path from "path";

const root = path.resolve(new URL("../../web-next", import.meta.url).pathname);
let failed = 0;
const fail = (m) => { failed++; console.error("PERF BUDGET:", m); };

const statsPath = path.join(root, ".next/diagnostics/route-bundle-stats.json");
if (fs.existsSync(statsPath)) {
  const budget = JSON.parse(fs.readFileSync(path.join(root, "perf-budget.json"), "utf8")).routes;
  for (const r of JSON.parse(fs.readFileSync(statsPath, "utf8"))) {
    const kb = Math.round(r.firstLoadUncompressedJsBytes / 1024);
    const cap = budget[r.route];
    if (cap === undefined) console.warn(`PERF BUDGET: no budget for new route ${r.route} (${kb} KB); add it to perf-budget.json`);
    else if (kb > cap) fail(`${r.route} first-load JS ${kb} KB > budget ${cap} KB`);
  }
} else console.warn("PERF BUDGET: no .next build found, skipping the bundle check");

const LEGACY = new Set(["onboarding-field-drift", "pqv-skeleton-shimmer", "prestige-glow-pulse", "premium-glow-pulse"]); // landing/onboarding + skeleton shimmer: converting them is tracked in docs/perf-budget.md
const BANNED = /(^|[\s;{])(background-position|top|left|right|bottom|width|height|box-shadow|filter|backdrop-filter|margin[a-z-]*|padding[a-z-]*)\s*:/;
function* cssFiles(dir) {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    if (e.name === "node_modules" || e.name === ".next") continue;
    const p = path.join(dir, e.name);
    if (e.isDirectory()) yield* cssFiles(p); else if (e.name.endsWith(".css")) yield p;
  }
}
for (const file of cssFiles(path.join(root, "src"))) {
  const css = fs.readFileSync(file, "utf8").replace(/\/\*[\s\S]*?\*\//g, "");
  const re = /@keyframes\s+([\w-]+)\s*\{/g; let m;
  while ((m = re.exec(css))) {
    let depth = 1, i = re.lastIndex;
    while (i < css.length && depth) { depth += css[i] === "{" ? 1 : css[i] === "}" ? -1 : 0; i++; }
    const body = css.slice(re.lastIndex, i);
    if (!LEGACY.has(m[1]) && BANNED.test(body)) fail(`${path.relative(root, file)}: @keyframes ${m[1]} animates a layout/paint property; use transform/opacity`);
  }
}
if (failed) process.exit(1);
console.log("perf budget ok");
