import { readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

import { RETIRED_TERM_ALLOWLIST, RETIRED_TERMS } from "./terms";

const ROOTS = [path.join(__dirname, ".."), path.join(__dirname, "../../../mobile/src")];
const SKIP_FILE = /(\.test\.|\.stories\.|legalContent|[\\/]terms\.ts$)/;

function walk(dir: string, out: string[] = []): string[] {
  for (const name of readdirSync(dir)) {
    const full = path.join(dir, name);
    if (statSync(full).isDirectory()) {
      if (name === "node_modules") continue;
      walk(full, out);
    } else if (/\.(ts|tsx)$/.test(name) && !SKIP_FILE.test(full)) {
      out.push(full);
    }
  }
  return out;
}

function stripComments(src: string): string {
  return src
    .replace(/\/\*[\s\S]*?\*\//g, (m) => m.replace(/[^\n]/g, " "))
    .replace(/(^|[^:"'`])\/\/.*$/gm, "$1");
}

/** String literals and JSX text on one line: what a user can actually read. */
function userVisibleStrings(src: string): string[] {
  const out: string[] = [];
  const lines = stripComments(src).split("\n");
  for (const line of lines) {
    if (/^\s*import\b|\bfrom\s+["']/.test(line)) continue;
    for (const m of line.matchAll(/(["'`])((?:\\.|(?!\1).)*)\1/g)) out.push(m[2]);
    for (const m of line.matchAll(/>([^<>{}]+)</g)) out.push(m[1]);
  }
  return out;
}

export function findRetiredTerms(): string[] {
  const hits: string[] = [];
  for (const root of ROOTS) {
    for (const file of walk(root)) {
      for (const text of userVisibleStrings(readFileSync(file, "utf8"))) {
        let scrubbed = text;
        for (const ok of RETIRED_TERM_ALLOWLIST) scrubbed = scrubbed.replace(new RegExp(ok, "g"), "");
        for (const term of RETIRED_TERMS) {
          if (term.pattern.test(scrubbed)) {
            hits.push(`${path.relative(path.join(__dirname, "../../.."), file)}: "${text.slice(0, 80)}" -> use "${term.use}"`);
          }
        }
      }
    }
  }
  return hits;
}

describe("product glossary (lib/terms.ts)", () => {
  it("has no retired term in user-visible strings on web or mobile", () => {
    expect(findRetiredTerms()).toEqual([]);
  });

  it("keeps the web and mobile glossary byte-identical", () => {
    const web = readFileSync(path.join(__dirname, "terms.ts"), "utf8");
    const mobile = readFileSync(path.join(__dirname, "../../../mobile/src/lib/terms.ts"), "utf8");
    expect(mobile).toBe(web);
  });
});
