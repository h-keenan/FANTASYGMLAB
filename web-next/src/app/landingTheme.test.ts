import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

const css = readFileSync(path.join(__dirname, "globals.css"), "utf8");

/** Body of the first rule whose selector text contains `selector`. */
function rule(selector: string): string {
  const start = css.indexOf(selector);
  expect(start, `selector ${selector}`).toBeGreaterThan(-1);
  const open = css.indexOf("{", start);
  return css.slice(open + 1, css.indexOf("}", open));
}

describe("landing forced-dark theme", () => {
  it("glass surfaces read tokens, not a hard-coded color-scheme branch", () => {
    const surface = rule(".glass-surface {");
    expect(surface).toContain("var(--glass-bg)");
    expect(surface).toContain("var(--glass-border)");
    expect(rule(".glass-input {")).toContain("var(--glass-input-bg)");
  });

  it("forced-dark scope redeclares the glass tokens and covers the page body (header)", () => {
    const start = css.indexOf(".fd-landing-dark,\n[data-onboarding-root],");
    expect(start).toBeGreaterThan(-1);
    const block = css.slice(start, css.indexOf("color-scheme: dark;", start));
    expect(block).toContain("body:has(.fd-landing-dark)");
    expect(block).toContain("--glass-bg:");
    expect(block).toContain("--glass-input-bg:");
    expect(block).toContain("--color-bg: #000000");
    expect(css).toMatch(/body:has\(\.fd-landing-dark\) \.brand-mark-icon \{\s*filter: invert\(1\)/);
  });

  it("showcase controls keep the dots centered with the pause button in a side column", () => {
    expect(rule(".landing-showcase-controls {")).toContain("grid-template-columns: 1fr auto 1fr");
    expect(rule(".landing-showcase-dots {")).toContain("grid-column: 2");
  });

  it("showcase slides size to a 3.5-slide peek", () => {
    expect(rule(".landing-shot {")).toContain("/ 3.5)");
  });
});
