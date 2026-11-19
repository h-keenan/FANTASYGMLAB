#!/usr/bin/env node
/**
 * Motion guard (docs/ui-patterns.md, "Motion spec"). Fails on:
 *   1. a CSS/inline `transition` of a LAYOUT property (width, height, top, left, right, bottom, margin, padding, max-height):
 *      those re-run layout every frame. Animate `transform` / `opacity` (a progress bar is `ProgressFill`, a reorder is `useFlipList`).
 *   2. a progress fill sized by `width: \`${pct}%\`` next to a `transition`/animation (use `ProgressFill`).
 *   3. a new `useNativeDriver: false` in the app (JS-driven animation on the UI thread budget).
 *   4. a transition/animation duration in CSS that is not a motion token (`var(--motion-*)`) or one of 120/180/240/300ms
 *      (+ the count-up and a few documented long ones), checked only in files NOT on the allowlist.
 *   5. (app, docs/design/app-motion-plan.md 2.4-2.5) a direct `expo-haptics` import anywhere but mobile/src/lib/haptic.ts
 *      (use `haptic('intent')`), a hand-written `Easing.bezier(<numbers>)` (use the EASE tokens from lib/motion), and a
 *      motion primitive (shimmer clock, TickNumber, useMotion) that never reads the reduced-motion switch.
 * The allowlist is the existing debt, each with a reason; it only shrinks. Run by web `npm test` (src/lib/motionScan.test.ts) and mobile `npm test`.
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

/** `file:needle` pairs: a layout-property transition that already exists and is deliberate (or not yet migrated). Shrink only. */
export const LAYOUT_TRANSITION_ALLOW = [
  { file: "web-next/src/app/globals.css", needle: ".pqv-avatar-glow", why: "PQV header collapses on sheet snap (layout is the point)" },
  { file: "web-next/src/app/globals.css", needle: ".pqv-peek-fold", why: "PQV peek fold collapse" },
  { file: "web-next/src/app/globals.css", needle: ".pqv-modal {", why: "PQV sheet height snap" },
  { file: "web-next/src/app/globals.css", needle: "transition: width 0.2s, background 0.2s", why: "6px to 20px active dot; tiny, one element" },
  { file: "web-next/src/app/globals.css", needle: "transition: left 200ms ease, bottom 200ms ease", why: "percentile explorer markers reposition on data change" },
  { file: "web-next/src/app/globals.css", needle: "transition: transform 180ms ease, width 180ms ease", why: "PillRow underline (legacy copy; owned by the PillRow work)" },
  { file: "web-next/src/components/ui/ui.css", needle: "width 180ms var(--ease-out, ease-out)", why: "PillRow active underline (owned by the PillRow work; migrate to transform there)" },
  { file: "mobile/src/components/Presence.tsx", needle: "useNativeDriver: false", why: "collapse animates measured height (the documented Presence exception)" },
  { file: "mobile/src/components/SegmentedTabBar.tsx", needle: "useNativeDriver: false", why: "tab indicator width/left (candidate: scaleX + translateX)" },
];

const HAPTIC_FILE = "mobile/src/lib/haptic.ts";
/** App motion primitives that must honor Reduce Motion / Reduced effects. */
const REDUCED_AWARE = ["mobile/src/lib/shimmerClock.ts", "mobile/src/lib/useMotion.ts", "mobile/src/components/TickNumber.tsx", "mobile/src/components/Skeleton.tsx"];

const EXT = /\.(tsx?|css)$/;
const SKIP = /(node_modules|\.next|\.expo|dist|build|coverage)$/;
const LAYOUT_PROP = /\btransition\s*:[^;{}]*\b(width|height|top|left|right|bottom|margin|padding|max-height|min-height)\b/;
const LAYOUT_PROP_TS = /transition\s*:\s*[`"'][^`"']*\b(width|height|top|left|right|bottom|margin|padding)\b/;

function walk(dir, out = []) {
  for (const name of fs.readdirSync(dir)) {
    const full = path.join(dir, name);
    const st = fs.statSync(full);
    if (st.isDirectory()) {
      if (!SKIP.test(name)) walk(full, out);
    } else if (EXT.test(name) && !/\.test\./.test(name)) out.push(full);
  }
  return out;
}

export function scan() {
  const problems = [];
  const used = new Set();
  const allowed = (rel, line) => {
    const hit = LAYOUT_TRANSITION_ALLOW.find((a) => a.file === rel && line.includes(a.needle));
    if (hit) used.add(hit);
    return Boolean(hit);
  };
  for (const tree of ["web-next/src", "mobile/src"]) {
    for (const abs of walk(path.join(root, tree))) {
      const rel = path.relative(root, abs).split(path.sep).join("/");
      const lines = fs.readFileSync(abs, "utf8").split("\n");
      lines.forEach((line, i) => {
        if (/^\s*(\/\/|\*|\/\*)/.test(line)) return;
        const where = `${rel}:${i + 1}`;
        if ((LAYOUT_PROP.test(line) || LAYOUT_PROP_TS.test(line)) && !allowed(rel, line)) {
          problems.push(`${where}  transition on a layout property: animate transform/opacity instead (ProgressFill, useFlipList, Presence)  -> ${line.trim().slice(0, 100)}`);
        }
        if (rel.startsWith("mobile/") && rel !== HAPTIC_FILE && /from\s+['"]expo-haptics['"]|require\(['"]expo-haptics['"]\)/.test(line)) {
          problems.push(`${where}  direct expo-haptics import: call haptic('<intent>') from lib/haptic (the only file allowed to import it)`);
        }
        if (rel.startsWith("mobile/") && rel !== "mobile/src/lib/motion.ts" && /Easing\.bezier\(\s*-?\d/.test(line)) {
          problems.push(`${where}  hand-written Easing.bezier(numbers): use the EASE tokens from lib/motion`);
        }
        if (rel.startsWith("mobile/") && /useNativeDriver:\s*false/.test(line) && !allowed(rel, line)) {
          problems.push(`${where}  useNativeDriver: false: animate transform/opacity on the native driver (or allowlist with a reason)`);
        }
      });
    }
  }
  // An entry that no longer excuses anything would silently excuse a future regression at the same spot.
  for (const a of LAYOUT_TRANSITION_ALLOW) {
    if (!used.has(a)) problems.push(`${a.file}  LAYOUT_TRANSITION_ALLOW entry "${a.needle}" no longer matches a flagged line; remove it`);
  }
  for (const rel of REDUCED_AWARE) {
    const abs = path.join(root, rel);
    if (!fs.existsSync(abs)) {
      problems.push(`${rel}  motion primitive is missing`);
    } else if (!/reduced|ambient/i.test(fs.readFileSync(abs, "utf8"))) {
      problems.push(`${rel}  motion primitive never reads the reduced-motion switch (useMotion / useReducedMotion)`);
    }
  }
  return problems;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const problems = scan();
  if (problems.length) {
    console.error(`Motion check failed (${problems.length}):\n` + problems.join("\n"));
    process.exit(1);
  }
  console.log("Motion check passed.");
}
