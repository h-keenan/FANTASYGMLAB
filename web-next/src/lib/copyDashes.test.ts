import { readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

/**
 * No em-dashes in user-visible copy (docs/ui-patterns.md "Copy casing and shared copy"; docs/audits/2026-11-bad-day-and-words.md).
 * Same scan as terms.test.ts: string literals and JSX text on one line. A lone "—" (the empty-value glyph) and a " — " used as a
 * separator token in code are not prose, so only a dash between two words fails. Fix the sentence (period or colon), do not allowlist.
 */
const ROOTS = [path.join(__dirname, ".."), path.join(__dirname, "../../../mobile/src")];
const SKIP_FILE = /(\.test\.|\.stories\.|legalContent|\.generated\.|[\\/]app[\\/]design[\\/]|DesignSystem)/;

function walk(dir: string, out: string[] = []): string[] {
  for (const name of readdirSync(dir)) {
    const full = path.join(dir, name);
    if (statSync(full).isDirectory()) {
      if (name !== "node_modules") walk(full, out);
    } else if (/\.(ts|tsx)$/.test(name) && !SKIP_FILE.test(full)) out.push(full);
  }
  return out;
}

function stripComments(src: string): string {
  return src
    .replace(/\/\*[\s\S]*?\*\//g, (m) => m.replace(/[^\n]/g, " "))
    .replace(/(^|[^:"'`])\/\/.*$/gm, "$1");
}

describe("no em-dash in UI copy", () => {
  it("has no spaced em-dash between words in a string or JSX text, on web or mobile", () => {
    const hits: string[] = [];
    for (const root of ROOTS) {
      for (const file of walk(root)) {
        stripComments(readFileSync(file, "utf8"))
          .split("\n")
          .forEach((line, index) => {
            if (/^\s*import\b|\bfrom\s+["']/.test(line)) return;
            const texts = [...line.matchAll(/(["'`])((?:\\.|(?!\1).)*)\1/g)].map((m) => m[2]).concat([...line.matchAll(/>([^<>{}]+)</g)].map((m) => m[1]));
            for (const text of texts) if (/\S\s—\s\S/.test(text)) hits.push(`${path.relative(path.join(__dirname, "../../.."), file)}:${index + 1}: ${text.slice(0, 80)}`);
          });
      }
    }
    expect(hits).toEqual([]);
  });
});
