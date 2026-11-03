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

  it("landing share-card variant swaps the h1 copy with a CSS flag, not a rerender", () => {
    expect(rule(".lp-share-only {")).toContain("display: none");
    expect(css).toContain("[data-share-landing] .lp-default-only");
  });

  it("landing CTAs and footer links keep 44px+ tap targets", () => {
    expect(rule(".lp .lp-cta > * {")).toContain("min-height: 52px");
    expect(rule(".lp-footer-links a {")).toContain("min-height: var(--touch-target-min)");
  });

  it("landing root is not its own scroll container (no phantom scroll space from the sweep)", () => {
    const start = css.lastIndexOf(".fd-landing-dark,\n[data-onboarding-root] {");
    const block = css.slice(start, css.indexOf("}", start));
    expect(block).toContain("overflow: clip");
    expect(block).not.toMatch(/^\s*overflow-y: auto;/m);
  });

  it("signed-in visitors never see the marketing blocks; onboarding steps scroll under a pinned footer", () => {
    expect(rule("[data-landing-signed-in] .lp-marketing {")).toContain("display: none");
    expect(rule(".onboarding-scroll {")).toContain("overflow-y: auto");
  });
});
