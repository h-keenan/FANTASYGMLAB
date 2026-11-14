import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

// Regression guard for the page tab strip (PillRow glass). Real cause of the "menu tabs are not centred" report:
//  1. the strip was `width: 100%` with negative side margins, so it was shifted left by the page gutter and stopped
//     ~2x gutter short of the right edge (page content peeked out on the right);
//  2. its scroller was a shrink-wrapped flex row, so tabs packed to the left;
//  3. the backing was a 46-78% translucent tint, so scrolled content showed through.
// Browser check: scripts/sim_layout_playwright/module_scan.mjs measures the strip edges on Team/Trades/League.
const css = readFileSync(join(__dirname, "../app/globals.css"), "utf8");
const block = (selector: string) => {
  const at = css.indexOf(`${selector} {`);
  expect(at).toBeGreaterThan(-1);
  return css.slice(at, css.indexOf("}", at));
};

describe("page tab strip CSS", () => {
  it("is full-bleed: explicit width of column plus both gutters", () => {
    const b = block(".pill-row-glass");
    expect(b).toMatch(/width:\s*calc\(100% \+ 2 \* var\(--pill-row-gutter\)\)/);
    expect(b).toMatch(/margin-inline:\s*calc\(var\(--pill-row-gutter\) \* -1\)/);
  });
  it("has an opaque base so nothing shows through", () => {
    expect(block(".pill-row-glass")).toMatch(/background-color:\s*var\(--color-bg\)/);
  });
  it("spreads tabs equally when they fit and scrolls only when they overflow", () => {
    const b = block(".pill-row-glass-scroller");
    expect(b).toMatch(/display:\s*grid/);
    expect(b).toMatch(/grid-auto-columns:\s*minmax\(max-content,\s*1fr\)/);
    expect(b).toMatch(/width:\s*100%/);
  });
});
