#!/usr/bin/env node
// Guard for the "?" standard (UI audit batch A, docs/ui-patterns.md "One InfoMark"). The only explainer affordance is
// InfoMark (web-next/src/components/ui/InfoMark.tsx, mobile/src/components/InfoMark.tsx): inline after the label it explains,
// never its own row, never over text. This fails CI when a retired variant comes back:
//
//   1. Retired component files must not exist: web BeginnerHelp / InfoTip / GlossaryNote, app BeginnerHelp / ScreenInfoNote / GlossaryNote.
//   2. Nothing may import or render them (<BeginnerHelp, <InfoTip, <GlossaryNote, <ScreenInfoNote, WhyCorner).
//   3. The tile-corner CSS (.ui-why-corner*, .ui-why-host) must not return.
//   4. An <InfoMark> tag must not be positioned absolutely (className "absolute", style position: 'absolute'), which is how a
//      corner "?" ends up over a label.
//   5. At most one <InfoMark per module is a review rule; the harness (scripts/sim_layout_playwright/module_scan.mjs) checks the
//      rendered result: no "?" alone on its own row, none overlapping text.
//
// Usage: node scripts/check_info_mark_usage.mjs   (exit 1 on any violation)
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const TREES = ["web-next/src", "mobile/src"];
const RETIRED_FILES = [
  "web-next/src/components/BeginnerHelp.tsx",
  "web-next/src/components/InfoTip.tsx",
  "web-next/src/components/GlossaryNote.tsx",
  "mobile/src/components/BeginnerHelp.tsx",
  "mobile/src/components/ScreenInfoNote.tsx",
  "mobile/src/components/GlossaryNote.tsx",
];
const RETIRED_USE = /<(BeginnerHelp|InfoTip|GlossaryNote|ScreenInfoNote|WhyCorner)\b|from\s+["'][^"']*\/(BeginnerHelp|InfoTip|GlossaryNote|ScreenInfoNote)["']|\bWhyCorner\b|ui-why-corner|ui-why-host/;
const ABSOLUTE_MARK = /<InfoMark\b[^>]*(\babsolute\b|position:\s*['"]absolute['"])/;

function* walk(dir) {
  for (const name of readdirSync(dir)) {
    if (name === "node_modules" || name.startsWith(".")) continue;
    const full = path.join(dir, name);
    if (statSync(full).isDirectory()) yield* walk(full);
    else if (/\.(tsx?|css)$/.test(name)) yield full;
  }
}

export function scan() {
  const problems = [];
  for (const rel of RETIRED_FILES) if (existsSync(path.join(ROOT, rel))) problems.push(`${rel}: retired component file still exists (use InfoMark)`);
  for (const tree of TREES) {
    for (const file of walk(path.join(ROOT, tree))) {
      const rel = path.relative(ROOT, file);
      if (/check_info_mark|InfoMark\.test|infoMarkGuard\.test/.test(rel)) continue;
      const lines = readFileSync(file, "utf8").split("\n");
      lines.forEach((line, i) => {
        if (/^\s*(\/\/|\*|\/\*)/.test(line)) return;
        if (RETIRED_USE.test(line)) problems.push(`${rel}:${i + 1}: retired "?" variant (${line.trim().slice(0, 80)}); use InfoMark`);
        if (ABSOLUTE_MARK.test(line)) problems.push(`${rel}:${i + 1}: InfoMark must sit inline after its label, never absolutely positioned`);
      });
    }
  }
  return problems;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const problems = scan();
  if (problems.length) {
    console.error(problems.join("\n"));
    console.error(`\n${problems.length} "?" standard violation(s). See docs/ui-patterns.md.`);
    process.exit(1);
  }
  console.log("info mark usage clean");
}
