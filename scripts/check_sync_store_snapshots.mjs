#!/usr/bin/env node
/**
 * useSyncExternalStore guard. React requires getSnapshot / getServerSnapshot to return a cached value: an inline arrow that
 * allocates (`() => []`, `() => ({ ... })`, `() => new Map()`) loops forever and logs "The result of getServerSnapshot should be
 * cached". Use a module-level constant (or a memoized snapshot) instead. The allowlist needs a reason and fails when stale.
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
/** `{ file, why }` entries whose inline allocation is proven safe. Stale entries fail. */
export const ALLOW = [];

const DIRS = ["web-next/src", "mobile/src"];
const SKIP = /(node_modules|\.next|\.expo|dist|build|coverage)$/;
const ALLOC = /^(\[|\{|new\s)/;

function walk(dir, out) {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name);
    if (SKIP.test(e.name)) continue;
    if (e.isDirectory()) walk(p, out);
    else if (/\.tsx?$/.test(e.name) && !/\.test\.tsx?$/.test(e.name)) out.push(p);
  }
  return out;
}

function splitArgs(text) {
  const args = [];
  let depth = 0, cur = "", q = null;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (q) { cur += c; if (c === "\\") cur += text[++i] ?? ""; else if (c === q) q = null; continue; }
    if (c === '"' || c === "'" || c === "`") { q = c; cur += c; continue; }
    if ("([{".includes(c)) depth++;
    if (")]}".includes(c)) depth--;
    if (c === "," && depth === 0) { args.push(cur); cur = ""; } else cur += c;
  }
  if (cur.trim()) args.push(cur);
  return args;
}

/** Line numbers of useSyncExternalStore calls whose snapshot args are inline arrows returning an object/array literal. */
export function findViolations(src) {
  const found = [];
  const re = /useSyncExternalStore\s*\(/g;
  let m;
  while ((m = re.exec(src))) {
    let depth = 1, i = re.lastIndex, q = null;
    for (; i < src.length && depth > 0; i++) {
      const c = src[i];
      if (q) { if (c === "\\") i++; else if (c === q) q = null; continue; }
      if (c === '"' || c === "'" || c === "`") q = c;
      else if (c === "(") depth++;
      else if (c === ")") depth--;
    }
    const args = splitArgs(src.slice(re.lastIndex, i - 1)).slice(1, 3);
    for (const arg of args) {
      const am = /^\s*\([^)]*\)\s*=>\s*(?:\(\s*)?([\s\S]*)$/.exec(arg);
      if (am && ALLOC.test(am[1].trim())) found.push(src.slice(0, m.index).split("\n").length);
    }
  }
  return found;
}

function main() {
  const problems = [];
  const hit = new Set();
  for (const d of DIRS) {
    for (const file of walk(path.join(root, d), [])) {
      const rel = path.relative(root, file);
      const lines = findViolations(fs.readFileSync(file, "utf8"));
      if (!lines.length) continue;
      if (ALLOW.some((a) => a.file === rel)) { hit.add(rel); continue; }
      problems.push(`${rel}:${lines.join(",")} inline useSyncExternalStore snapshot allocates; hoist a constant or memoize`);
    }
  }
  for (const a of ALLOW) {
    if (!a.why) problems.push(`allowlist entry ${a.file} has no reason`);
    if (!hit.has(a.file)) problems.push(`stale allowlist entry ${a.file}: no violation left, remove it`);
  }
  if (problems.length) { console.error(problems.join("\n")); process.exit(1); }
  console.log("check_sync_store_snapshots: ok");
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) main();
