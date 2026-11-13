import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

/**
 * UI audit guard (docs/audits/2026-11-ui-audit-2.md): the app's text floor is 11px on web (mobile's is 12 and has its own
 * guard). Sub-11px Tailwind literals are acknowledged debt: this ratchet only ever goes DOWN. New UI must use the shared
 * components/tokens instead of inventing a micro size. Raise nothing here; lower the baseline when you fix some.
 */
const SRC = join(process.cwd(), "src");
const TINY = /text-\[(?:0\.5rem|0\.5625rem|0\.625rem|9px|10px)\]/g; // 8-10px
const BASELINE = 32; // measured 2026-11-13 after the PlayerListRow stat labels moved to 11px

function walk(dir: string, out: string[] = []): string[] {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) walk(p, out);
    else if (/\.tsx$/.test(name) && !/\.test\./.test(name) && !p.includes("/design/")) out.push(p);
  }
  return out;
}

describe("ui sizing guard", () => {
  it("does not add sub-11px text literals (ratchet)", () => {
    let count = 0;
    for (const file of walk(SRC)) count += (readFileSync(file, "utf8").match(TINY) ?? []).length;
    expect(count).toBeLessThanOrEqual(BASELINE);
  });
});
