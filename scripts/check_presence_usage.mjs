#!/usr/bin/env node
// Guard for the shared Presence primitive (docs/ui-patterns.md "Presence").
//
// Anything that expands, collapses, appears or disappears goes through `Collapse` / `Presence` / `PresenceList` (web
// `components/ui/Presence.tsx`, app `components/Presence.tsx`) so nothing pops. This scan fails on a NEW hand-rolled
// expander body: a conditional render keyed on an open/expanded-style state variable,
//
//     {open ? (<div>...</div>) : null}        {expanded && <Panel />}        {showWhy ? <p>..</p> : null}
//
// outside the shared module. Fix it with `<Collapse open={open}>...</Collapse>`. A conditional that is genuinely not an
// expander (a popover anchored to its trigger, a Modal/Sheet mount whose own shell animates, a one-off label swap) goes in
// ALLOWED below with a reason; the list only shrinks. LayoutAnimation is also banned outside the files listed (Collapse
// measures height itself; a second animator on the same toggle fights it).
//
// Usage: node scripts/check_presence_usage.mjs   (exit 1 on any violation)
import { readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const TREES = ["web-next/src", "mobile/src"];

// The state names that mean "an expander body": an open flag, never a data check.
const STATE = "(?:open|opened|isOpen|expanded|isExpanded|showWhy|showMore|showRest|showAll|showDetail|showDetails|showBreakdown)";
const PATTERNS = [
  new RegExp(String.raw`\{\s*${STATE}\s*\?\s*(?:\(|<|$)`),
  new RegExp(String.raw`\{\s*${STATE}\s*&&\s*(?:\(|<|$)`),
];

// Files allowed to keep a flagged conditional, with the reason. Shrink this list, never grow it to silence a new expander.
export const ALLOWED = {
  // Popovers / dropdowns anchored to a trigger (they position against it; the wrapper transform would re-anchor them).
  "web-next/src/components/AlertsDropdown.tsx": "dropdown with its own overlay shell",
  "web-next/src/components/TrialAccountGate.tsx": "swaps between two forms (not an expander)",
  // Modal / sheet mounts: the shell animates itself (Sheet / SheetModal), the flag only mounts it.
  "web-next/src/components/SimGameLeague.tsx": "mounts a matchup sheet",
  "web-next/src/components/SimRealism.tsx": "mounts a sheet",
  "mobile/src/components/SimGameLeague.tsx": "mounts a matchup sheet",
  "mobile/src/components/SimRealism.tsx": "mounts a sheet",
  // The shared module itself.
  "web-next/src/components/ui/Presence.tsx": "the primitive",
  "mobile/src/components/Presence.tsx": "the primitive",
};

// LayoutAnimation (RN) animates whole-tree layout changes: only these use it, for non-expander moves.
export const LAYOUT_ANIMATION_ALLOWED = [
  "mobile/src/components/PlayerAccordionRow.tsx", // animateRowExpand (the sim Move strip, fairness meter, trade tweak)
  "mobile/src/components/PlayerQuickViewSheet.tsx", // peek sheet snap
];

function walk(dir, out = []) {
  for (const name of readdirSync(dir)) {
    const full = path.join(dir, name);
    const st = statSync(full);
    if (st.isDirectory()) {
      if (name === "node_modules" || name === ".next") continue;
      walk(full, out);
    } else if (/\.tsx$/.test(name) && !/\.test\.tsx$/.test(name)) out.push(full);
  }
  return out;
}

const problems = [];
const usedAllow = new Set();
const usedLayoutAnimation = new Set();
for (const tree of TREES) {
  for (const file of walk(path.join(root, tree))) {
    const rel = path.relative(root, file).split(path.sep).join("/");
    const lines = readFileSync(file, "utf8").split("\n");
    lines.forEach((line, i) => {
      const code = line.trim();
      if (code.startsWith("//") || code.startsWith("*") || code.startsWith("/*")) return;
      if (PATTERNS.some((re) => re.test(line))) {
        if (rel in ALLOWED) usedAllow.add(rel);
        else problems.push(`${rel}:${i + 1}: hand-rolled expander \`${code.slice(0, 70)}\` (use <Collapse open={...}> from the shared Presence module)`);
      }
      if (/LayoutAnimation\.configureNext/.test(line) && rel.startsWith("mobile/")) {
        if (LAYOUT_ANIMATION_ALLOWED.includes(rel)) usedLayoutAnimation.add(rel);
        else problems.push(`${rel}:${i + 1}: LayoutAnimation outside the allowlist (use <Collapse>/<Presence>)`);
      }
    });
  }
}
for (const rel of Object.keys(ALLOWED)) if (!usedAllow.has(rel) && !/Presence\.tsx$/.test(rel)) problems.push(`ALLOWED entry no longer needed (remove it): ${rel}`);
for (const rel of LAYOUT_ANIMATION_ALLOWED) if (!usedLayoutAnimation.has(rel)) problems.push(`LAYOUT_ANIMATION_ALLOWED entry no longer needed (remove it): ${rel}`);

if (problems.length) {
  console.error(problems.join("\n"));
  process.exit(1);
}
console.log("Presence usage check passed.");
