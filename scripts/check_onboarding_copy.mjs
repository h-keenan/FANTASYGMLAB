#!/usr/bin/env node
// Guard: no em-dash (U+2014) in user-facing onboarding copy (house rule: no em-dashes in UI copy).
// Scans the onboarding screens and the shared experience copy on web and mobile. Comments are ignored (they may use
// em-dashes freely); only string literals / JSX text on code lines count.
//
// Usage: node scripts/check_onboarding_copy.mjs   (exit 1 on any violation)
import { readFileSync, existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const FILES = [
  "web-next/src/components/OnboardingCarousel.tsx",
  "web-next/src/components/OnboardingValueSlides.tsx",
  "web-next/src/components/OnboardingShell.tsx",
  "web-next/src/lib/onboardingFeatures.ts",
  "web-next/src/lib/experienceCopy.ts",
  "mobile/src/screens/OnboardingScreen.tsx",
  "mobile/src/lib/experienceCopy.ts",
];

const bad = [];
for (const rel of FILES) {
  const full = path.join(ROOT, rel);
  if (!existsSync(full)) continue;
  let inBlock = false;
  readFileSync(full, "utf8")
    .split("\n")
    .forEach((line, i) => {
      let code = line;
      if (inBlock) {
        const end = code.indexOf("*/");
        if (end === -1) return;
        inBlock = false;
        code = code.slice(end + 2);
      }
      code = code.replace(/\/\*.*?\*\//g, "");
      const open = code.indexOf("/*");
      if (open !== -1) {
        inBlock = true;
        code = code.slice(0, open);
      }
      code = code.replace(/(^|\s)\/\/.*$/, "$1");
      if (code.includes("—") || /&mdash;|\\u2014/.test(code)) bad.push(`${rel}:${i + 1}: ${line.trim()}`);
    });
}
if (bad.length) {
  console.error("Em-dash in onboarding copy (use a colon, period or comma):\n" + bad.join("\n"));
  process.exit(1);
}
console.log("check_onboarding_copy: ok");
