import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

/**
 * Regression (coridian_, 2026-11-14): desktop Matchup showed TWO header bars. ShellHeader is `.shell-header md:hidden`,
 * but `.shell-header { display: flex }` is unlayered CSS and Tailwind v4 utilities live in @layer utilities, so the
 * component rule won and the phone header rendered above the desktop Header on every page. One guard in globals.css
 * keeps every `md:hidden` element hidden from 768px up, whatever display its own class sets.
 */
describe("phone-only chrome stays off desktop", () => {
  const css = readFileSync(path.join(__dirname, "globals.css"), "utf8");

  it("has an unlayered md:hidden guard from 768px", () => {
    expect(css).toMatch(/@media \(min-width: 768px\) \{\s*\.md\\:hidden \{ display: none !important; \}\s*\}/);
  });

  it("ShellHeader is still a phone-only (md:hidden) header", () => {
    const src = readFileSync(path.join(__dirname, "..", "components", "ShellHeader.tsx"), "utf8");
    expect(src).toContain('className="shell-header md:hidden"');
  });
});
