import { readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

const COMPONENTS = path.join(__dirname, "../components");

function walk(dir: string, out: string[] = []): string[] {
  for (const name of readdirSync(dir)) {
    const full = path.join(dir, name);
    if (statSync(full).isDirectory()) walk(full, out);
    else if (/\.tsx$/.test(name) && !/\.test\./.test(name)) out.push(full);
  }
  return out;
}

/** The opening tag text of every `<select`, balancing `{}` so `=>` in props is not read as the tag end. */
function selectOpeningTags(src: string): string[] {
  const tags: string[] = [];
  let from = 0;
  for (;;) {
    const start = src.indexOf("<select", from);
    if (start === -1) return tags;
    let depth = 0;
    let i = start;
    for (; i < src.length; i += 1) {
      const ch = src[i];
      if (ch === "{") depth += 1;
      else if (ch === "}") depth -= 1;
      else if (ch === ">" && depth === 0 && src[i - 1] !== "=") break;
    }
    const before = src.slice(0, start);
    const wrapped = before.lastIndexOf("<label") > before.lastIndexOf("</label>");
    tags.push(wrapped ? `${src.slice(start, i + 1)} aria-label="wrapped-in-label"` : src.slice(start, i + 1));
    from = i + 1;
  }
}

describe("native <select> accessibility", () => {
  it("gives every <select> in components an accessible name (aria-label, aria-labelledby, id for a <label>, being wrapped in a <label>, or a props spread from a wrapper)", () => {
    const unlabeled: string[] = [];
    for (const file of walk(COMPONENTS)) {
      for (const tag of selectOpeningTags(readFileSync(file, "utf8"))) {
        if (!/\baria-label=|\baria-labelledby=|\bid=|\{\.\.\.\w+\}/.test(tag)) {
          unlabeled.push(`${path.relative(COMPONENTS, file)}: ${tag.replace(/\s+/g, " ").slice(0, 100)}`);
        }
      }
    }
    expect(unlabeled).toEqual([]);
  });
});
