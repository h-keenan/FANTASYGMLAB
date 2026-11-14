import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

// Regression guard for "the footer / GM orb floats mid-screen when scrolling" (owner screenshots, 2026-11-14).
// Root cause: every bottom bar is `position: sticky; bottom: 0`, and sticky is clamped to its PARENT's box. html and
// body had `height: 100%`, so the body box was exactly one viewport tall while the content overflowed it; the sticky
// footer / orb (a child of body, or of a flex column sized from it) ran out of parent one screen down and scrolled
// away with content still below it. A flex-1 (basis 0) chain had the same effect one level lower. The fix is
// structural, so these assert the structure: bottom chrome is one mechanism and its ancestors span the document.
const read = (f: string) => readFileSync(join(__dirname, "..", f), "utf8");

function rule(css: string, selector: string): string {
  const i = css.indexOf(`${selector} {`);
  expect(i, `${selector} rule`).toBeGreaterThanOrEqual(0);
  return css.slice(i, css.indexOf("}", i));
}

describe("bottom chrome: one sticky mechanism over a document-tall ancestor chain", () => {
  it("html and body never get a fixed height", () => {
    const css = read("app/globals.css");
    expect(rule(css, "html")).not.toMatch(/(^|[;\s])height:/);
    expect(rule(css, "body")).not.toMatch(/(^|[;\s])height:/);
    expect(rule(css, "body")).toContain("min-height: 100dvh");
    const layout = read("app/layout.tsx");
    expect(layout).not.toMatch(/<html[^>]*\bh-full\b/);
    expect(layout).not.toMatch(/<body[^>]*[" ](h-full|h-screen|h-dvh)[" ]/);
    expect(layout).toMatch(/<body className="min-h-dvh flex flex-col">/);
  });
  it("the app column and the Sim column grow with content (flex-auto, not flex-1 / min-h-0 / overflow)", () => {
    const shell = read("components/AppContentShell.tsx");
    expect(shell).toMatch(/flex flex-col flex-auto/);
    const sim = read("components/SimGameContent.tsx");
    expect(sim).toMatch(/flex flex-auto flex-col gap-3/);
    expect(sim).not.toMatch(/className=\{`flex flex-1 flex-col gap-3/);
    expect(sim).not.toMatch(/data-testid="sim-bottom-stack"[\s\S]{0,0}min-h-0/);
  });
  it("the stack and the rail are sticky, bottom 0, in flow; nothing bottom-pinned is position: fixed", () => {
    const css = read("components/ui/ui.css");
    for (const sel of [".bottom-stack", ".bottom-rail"]) {
      const r = rule(css, sel);
      expect(r, sel).toContain("position: sticky");
      expect(r, sel).toContain("bottom: 0");
      expect(r, sel).not.toMatch(/position:\s*fixed/);
    }
    const orb = read("components/GmOrb.tsx");
    expect(orb).toContain('className="bottom-rail md:hidden"');
    expect(orb).not.toMatch(/position:\s*"fixed"/);
    expect(orb).not.toMatch(/visualViewport\??\./);
  });
});
