#!/usr/bin/env node
// Casing drift guard for section and module headings (docs/ui-patterns.md, "Copy casing").
//
// Rule: headings use sentence case. The same heading must not appear in the web and the app differing only by
// letter case ("Choose Your Plan" vs "Choose your plan"). Named product surfaces and glossary terms that legitimately
// read differently in a heading and in a label go in ALLOW (lowercased).
//
// Scope: string-literal `title=` on SectionHeading / CompactModule / SheetHeader, and <SectionHeading>Text</SectionHeading>.
//
// Usage: node scripts/check_copy_casing.mjs   (exit 1 on any case-only mismatch)
import { readdirSync, readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

// Lowercased headings allowed to differ in case between clients.
const ALLOW = new Set(["playoff odds"]);

function* walk(dir) {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    if (entry.name === "node_modules" || entry.name === ".next") continue;
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) yield* walk(full);
    else if (entry.name.endsWith(".tsx") && !entry.name.includes(".test.")) yield full;
  }
}

function headings(base) {
  const found = new Map();
  const add = (text, file) => {
    if (!found.has(text)) found.set(text, file);
  };
  for (const file of walk(path.join(root, base))) {
    const src = readFileSync(file, "utf8");
    for (const m of src.matchAll(/<(?:SectionHeading|CompactModule|SheetHeader)\b[^>]*?\btitle=(?:\{\s*)?["']([^"'{}]+)["']/g)) add(m[1], file);
    for (const m of src.matchAll(/<SectionHeading\b[^>]*>\s*([A-Z][^<{}]+?)\s*<\/SectionHeading>/g)) add(m[1], file);
  }
  return found;
}

const app = headings("mobile/src");
const web = headings("web-next/src");
const webByLower = new Map();
for (const [text, file] of web) webByLower.set(text.toLowerCase(), { text, file });

const problems = [];
const usedAllow = new Set();
for (const [text, file] of app) {
  const lower = text.toLowerCase();
  const other = webByLower.get(lower);
  const mismatch = other && other.text !== text && !web.has(text);
  if (ALLOW.has(lower)) {
    if (mismatch) usedAllow.add(lower);
    continue;
  }
  if (mismatch) {
    problems.push(`"${text}" (${path.relative(root, file)}) vs "${other.text}" (${path.relative(root, other.file)})`);
  }
}

// An ALLOW entry that excuses no live mismatch would silently excuse a future one: it only shrinks.
for (const lower of ALLOW) if (!usedAllow.has(lower)) problems.push(`ALLOW entry "${lower}" no longer excuses a case-only mismatch (remove it)`);

if (problems.length) {
  console.error("Heading casing differs between web and app (use sentence case, same string in both):");
  for (const p of problems) console.error(`  ${p}`);
  process.exit(1);
}
console.log(`Heading casing check passed (${app.size} app / ${web.size} web headings).`);
