#!/usr/bin/env node
// Guard for "Tabs, not dropdowns" (docs/ui-patterns.md): a view switch with FOUR OR FEWER options is the shared compact
// segmented tabs (`ViewTabs`), never a `ViewSelect` dropdown. A dropdown is only for five or more options (seasons, weeks, long
// lists). This fails when a `<ViewSelect ...>` has a literal options array of 4 or fewer entries, or when its options are not a
// literal (a computed list such as weeks) and the tag carries no `view-select-ok: reason` comment on it or the line above.
//
// Usage: node scripts/check_view_select.mjs   (exit 1 on any violation)
import { readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const TREES = ["web-next/src", "mobile/src"];
const MAX_TABS = 4;
const SKIP = /(\.test\.|check_view_select|components\/ui\/ViewSelect\.tsx|components\/PageControlRow\.tsx)/;
// The shared form <Select> wrapper itself; its callers are what get judged.
const RAW_SELECT_SKIP = /components\/Input\.tsx$/;

function* walk(dir) {
  for (const name of readdirSync(dir)) {
    if (name === "node_modules" || name.startsWith(".")) continue;
    const full = path.join(dir, name);
    if (statSync(full).isDirectory()) yield* walk(full);
    else if (/\.tsx$/.test(name)) yield full;
  }
}

/** The text of the JSX tag starting at `start` (a `<ViewSelect`), up to its closing `>` / `/>` outside braces. */
function tagText(src, start) {
  let depth = 0;
  for (let i = start; i < src.length; i++) {
    const c = src[i];
    if (c === "{") depth++;
    else if (c === "}") depth--;
    else if (c === ">" && depth === 0 && src[i - 1] !== "=") return src.slice(start, i + 1);
  }
  return src.slice(start);
}

/** Option count of a literal `options={[ ... ]}` / `options={['a', 'b']}`, or null when the options are computed. */
function literalOptionCount(tag) {
  const m = /options=\{\s*\[([\s\S]*?)\]\s*\}/.exec(tag);
  if (!m) return null;
  const body = m[1];
  if (/\.map\(|\.\.\./.test(body)) return null;
  const objects = (body.match(/\{\s*value\s*:/g) ?? []).length;
  if (objects > 0) return objects;
  return (body.match(/(["'])(?:(?!\1).)*\1/g) ?? []).length;
}

export function scanText(rel, src) {
  const problems = [];
  const lines = src.split("\n");
  const re = /<ViewSelect(?=[\s<>/])/g;
  let m;
  while ((m = re.exec(src))) {
    const line = src.slice(0, m.index).split("\n").length;
    const tag = tagText(src, m.index);
    const ok = /view-select-ok/.test(tag) || /view-select-ok/.test(lines[line - 1] ?? "") || /view-select-ok/.test(lines[line - 2] ?? "");
    const count = literalOptionCount(tag);
    if (count !== null && count <= MAX_TABS) {
      problems.push(`${rel}:${line}: ViewSelect with ${count} options; ${MAX_TABS} or fewer are the shared compact tabs (ViewTabs), not a dropdown`);
    } else if (count === null && !ok) {
      problems.push(`${rel}:${line}: ViewSelect with computed options; use ViewTabs for 4 or fewer, or mark a 5+ list (weeks, seasons) with // view-select-ok: reason`);
    }
  }
  if (!RAW_SELECT_SKIP.test(rel)) problems.push(...scanRawSelects(rel, src, lines));
  return problems;
}

/**
 * A raw `<select>` (or `<Select>` from Input.tsx is fine: it is a form field) used as a view / filter switch slips past the
 * ViewSelect check above. Standing rule: tabs or chips, never dropdowns. A raw `<select>` fails unless it is a labelled form
 * field (carries an `id=`, wired to a <label htmlFor>) or has a `view-select-ok: reason` comment on it or the line above.
 */
function scanRawSelects(rel, src, lines) {
  const problems = [];
  const re = /<select(?=[\s>])/g;
  let m;
  while ((m = re.exec(src))) {
    const line = src.slice(0, m.index).split("\n").length;
    const tag = tagText(src, m.index);
    const ok = /view-select-ok/.test(tag) || /view-select-ok/.test(lines[line - 1] ?? "") || /view-select-ok/.test(lines[line - 2] ?? "");
    if (ok || /\sid=/.test(tag)) continue;
    problems.push(`${rel}:${line}: raw <select> used as a view/filter switch; use chips or ViewTabs (tabs/chips, never dropdowns), or mark a real form field / 5+ list with // view-select-ok: reason`);
  }
  return problems;
}

export function scan() {
  const problems = [];
  for (const tree of TREES) {
    for (const file of walk(path.join(ROOT, tree))) {
      const rel = path.relative(ROOT, file);
      if (SKIP.test(rel)) continue;
      problems.push(...scanText(rel, readFileSync(file, "utf8")));
    }
  }
  return problems;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const problems = scan();
  if (problems.length) {
    console.error(`View select check failed (${problems.length}):`);
    for (const p of problems) console.error(`  - ${p}`);
    process.exit(1);
  }
  console.log("View select check passed.");
}
