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
      // Phones: the bar sits inside the game's sticky `.bottom-stack` (see below); md+ it sticks itself.
      expect(src, f).toContain("md:sticky");
      expect(src, f).not.toMatch(/className="[^"]*\bfixed\b/);
    }
  });
  it("the game's bottom stack is sticky in flow and its orb is absolute inside it", () => {
    const css = read("ui/ui.css");
    const stack = css.slice(css.indexOf(".bottom-stack {"), css.indexOf("}", css.indexOf(".bottom-stack {")));
    expect(stack).toContain("position: sticky");
    expect(stack).toContain("env(safe-area-inset-bottom");
    const dock = css.slice(css.indexOf(".game-orb-dock {"), css.indexOf("}", css.indexOf(".game-orb-dock {")));
    expect(dock).toContain("position: absolute");
    for (const f of ["SimGameOrb.tsx", "SimGameHeader.tsx", "ui/BottomTabBar.tsx"]) {
      expect(read(f), f).not.toMatch(/className="[^"]*\bfixed\b/);
      expect(read(f), f).not.toContain("visualViewport");
    }
    expect(css).not.toMatch(/\.(bottom-stack|game-orb|bottom-tab-bar|action-pill)[^{]*\{[^}]*position:\s*fixed/);
  });
  it("GmOrb trigger button is not fixed", () => {
    const src = read("GmOrb.tsx");
    expect(src).toContain('position: "sticky"');
    expect(src).toContain('className="absolute left-1/2 flex items-center justify-center"');
  });
});
