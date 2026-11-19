#!/usr/bin/env node
// Guard: there is exactly ONE weekly-points chart implementation (docs/ui-patterns.md, "One weekly chart"):
// `WeeklyPointsChart` / `WeeklyPointsPanel` (a thin adapter) over `TrendChart` and `lib/chartSeries.ts`, on web and in the app.
// Desk PQV, Player Compare and the Sim player card all feed it the same series shape (actual, projection band, bye / injured /
// inactive gap kinds). This fails CI when a second implementation appears:
//   1. a file other than the shared chart files imports a RUNTIME value from chartSeries (type-only imports are fine), which is
//      how a private chart would reuse the data rules without going through TrendChart;
//   2. a charting library (recharts, victory, chart.js, d3-shape, react-native-chart-kit) is imported anywhere;
//   3. a component file whose name looks like a weekly / points / sim chart is not one of the shared files.
// Use `// weekly-chart-ok: reason` on the line (or the line above) only for a real non-weekly chart.
//
// Usage: node scripts/check_weekly_chart.mjs   (exit 1 on any violation)
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const TREES = ["web-next/src", "mobile/src"];
const SHARED = new Set([
  "web-next/src/components/ui/TrendChart.tsx",
  "web-next/src/components/WeeklyPointsChart.tsx",
  "web-next/src/components/WeeklyPointsChartLazy.tsx",
  "mobile/src/components/TrendChart.tsx",
  "mobile/src/components/WeeklyPointsChart.tsx",
]);
const CHART_LIBS = /from\s+["'](recharts|victory[\w-]*|chart\.js|react-chartjs-2|d3-shape|d3|react-native-chart-kit|react-native-gifted-charts)["']/;
const NAME = /(Weekly|Points|Sim|Sparkline|Trend|Line)\w*Chart\w*\.tsx$/i;
// Rating / rank history is a different series (not weekly points) but still draws through the shared TrendChart.
const NAME_OK = /(RatingHistoryChart|WeeklyPointsChart|TrendChart|DepthChart|depth)/i;
const OK = /weekly-chart-ok/;

function* walk(dir) {
  for (const name of readdirSync(dir)) {
    if (name === "node_modules" || name.startsWith(".")) continue;
    const full = path.join(dir, name);
    if (statSync(full).isDirectory()) yield* walk(full);
    else if (/\.tsx?$/.test(name)) yield full;
  }
}

export function scanText(rel, src) {
  const problems = [];
  if (SHARED.has(rel) || /\.test\./.test(rel) || /\/lib\/chartSeries\.ts$/.test(rel)) return problems;
  const lines = src.split("\n");
  lines.forEach((line, i) => {
    if (OK.test(line) || (i > 0 && OK.test(lines[i - 1]))) return;
    if (CHART_LIBS.test(line)) problems.push(`${rel}:${i + 1}: charting library import; the one chart is TrendChart (via WeeklyPointsChart)`);
  });
  // Runtime (non type-only) imports from chartSeries.
  for (const m of src.matchAll(/import\s+(type\s+)?\{([^}]*)\}\s+from\s+["'][^"']*chartSeries["']/g)) {
    if (m[1]) continue;
    const names = m[2].split(",").map((n) => n.trim()).filter(Boolean);
    const runtime = names.filter((n) => !/^type\s/.test(n));
    if (runtime.length > 0 && !OK.test(src.slice(Math.max(0, m.index - 120), m.index + m[0].length))) {
      problems.push(`${rel}: imports ${runtime.join(", ")} from chartSeries; only TrendChart / WeeklyPointsChart draw or shape weekly series (feed them the series instead)`);
    }
  }
  return problems;
}

export function scan() {
  const problems = [];
  // SHARED excuses a whole file; a path that no longer exists would silently excuse a future file at that path.
  for (const rel of SHARED) if (!existsSync(path.join(ROOT, rel))) problems.push(`${rel}: SHARED entry no longer exists (remove it)`);
  for (const tree of TREES) {
    for (const file of walk(path.join(ROOT, tree))) {
      const rel = path.relative(ROOT, file);
      if (!SHARED.has(rel) && NAME.test(rel) && !NAME_OK.test(rel) && !/\.test\./.test(rel)) {
        problems.push(`${rel}: a second chart component; weekly points use WeeklyPointsChart / WeeklyPointsPanel (TrendChart), including in Sim`);
      }
      problems.push(...scanText(rel, readFileSync(file, "utf8")));
    }
  }
  return problems;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const problems = scan();
  if (problems.length) {
    console.error(`Weekly chart check failed (${problems.length}):`);
    for (const p of problems) console.error(`  - ${p}`);
    process.exit(1);
  }
  console.log("Weekly chart check passed.");
}
