import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import { BAR_CONTENT_CLEARANCE, BAR_METRICS, BAR_PILL_HEIGHT, BAR_REGION_HEIGHT } from "./bottomBarMetrics";

const css = readFileSync(join(__dirname, "../components/ui/ui.css"), "utf8");
const globals = readFileSync(join(__dirname, "../app/globals.css"), "utf8");
const cssPx = (name: string) => {
  const m = css.match(new RegExp(`--${name}:\\s*([0-9.]+)px`));
  if (!m) throw new Error(`--${name} missing from ui.css`);
  return Number(m[1]);
};

describe("bottom bar metrics (shared with mobile)", () => {
  it("the CSS custom properties equal the shared constants", () => {
    expect(cssPx("bar-side-inset")).toBe(BAR_METRICS.sideInset);
    expect(cssPx("bar-pill-bottom-gap")).toBe(BAR_METRICS.pillBottomGap);
    expect(cssPx("bar-pill-padding")).toBe(BAR_METRICS.pillPadding);
    expect(cssPx("bar-button-min-height")).toBe(BAR_METRICS.buttonMinHeight);
    expect(cssPx("bar-orb-size")).toBe(BAR_METRICS.orbSize);
    expect(cssPx("bar-orb-gap")).toBe(BAR_METRICS.orbGap);
    expect(cssPx("bar-tab-height")).toBe(BAR_METRICS.tabBarHeight);
    expect(cssPx("bar-header-height")).toBe(BAR_METRICS.headerHeight);
  });

  it("the pill, the orb dock and the headers use the variables, not their own numbers", () => {
    expect(css).toContain("margin: 0 var(--bar-side-inset) var(--bar-pill-bottom-gap)");
    expect(css).toContain("width: var(--bar-orb-size)");
    expect(globals.match(/min-height: var\(--bar-header-height\)/g)?.length).toBeGreaterThanOrEqual(1);
  });

  it("the pill reads its inset, gap and tap height from the shared variables", () => {
    expect(css).toContain("margin: 0 var(--bar-side-inset) calc(var(--bar-pill-bottom-gap) + env(safe-area-inset-bottom");
    expect(css).toContain("width: var(--bar-button-min-height)");
  });

  it("derived heights add up and every button is a real tap target", () => {
    expect(BAR_PILL_HEIGHT).toBe(54);
    expect(BAR_REGION_HEIGHT).toBe(62);
    expect(BAR_CONTENT_CLEARANCE).toBe(62 + 56 + 4);
    expect(BAR_METRICS.buttonMinHeight).toBeGreaterThanOrEqual(44);
    expect(BAR_METRICS.orbSize).toBeGreaterThanOrEqual(44);
  });
});
