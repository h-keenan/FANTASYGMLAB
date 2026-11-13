import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

// iOS Safari mis-anchors `position: fixed` bottom elements to the layout
// viewport mid-scroll (owner screenshots, 2026-11): the GM orb and the Sim
// action bars floated mid-screen. They are sticky in-flow instead. Guard
// against reintroducing `fixed` on them.
const read = (f: string) => readFileSync(join(__dirname, f), "utf8");

describe("bottom-pinned chrome stays sticky, not fixed", () => {
  it("SimActionBar / SimOffseasonBar", () => {
    for (const f of ["SimActionBar.tsx", "SimOffseasonBar.tsx"]) {
      const src = read(f);
      expect(src, f).toContain("sticky bottom-0");
      expect(src, f).not.toMatch(/className="[^"]*\bfixed\b/);
    }
  });
  it("GmOrb trigger button is not fixed", () => {
    const src = read("GmOrb.tsx");
    expect(src).toContain('position: "sticky"');
    expect(src).toContain('className="absolute left-1/2 flex items-center justify-center"');
  });
});
