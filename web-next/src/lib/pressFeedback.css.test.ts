import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

import { PRESS } from "./motion";

const css = readFileSync(resolve(process.cwd(), "src/app/globals.css"), "utf8");

describe("press feedback (globals.css) mirrors lib/motion.ts PRESS", () => {
  it("defines the tokens from PRESS and one zero-specificity :active rule", () => {
    expect(css).toContain(`--press-scale: ${PRESS.scale}`);
    expect(css).toContain(`--press-opacity: ${PRESS.opacity}`);
    expect(css).toMatch(/:where\(button, \[role="button"\][^)]*\)[^{]*:active \{\s*scale: var\(--press-scale\);\s*opacity: var\(--press-opacity\);/);
  });
  it("reduced motion removes the shrink but keeps the fade", () => {
    expect(css).toMatch(/prefers-reduced-motion: reduce\) \{[\s\S]*?:root \{ --press-scale: 1; \}/);
  });
});
