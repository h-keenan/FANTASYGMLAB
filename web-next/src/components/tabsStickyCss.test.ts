import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

const css = readFileSync(path.join(process.cwd(), "src/app/globals.css"), "utf8");
const rule = (sel: string) => css.match(new RegExp(`\\n${sel.replace(/[.:]/g, "\\$&")} \\{[^}]*\\}`))?.[0] ?? "";

describe("sticky tab strip CSS contract (geometry guard: scripts/sim_layout_playwright/sheet_tabs_dock.mjs)", () => {
  it("docks via the measured --tabs-top (container padding subtracted), never a bare top: 0", () => {
    const r = rule(".tabs-sticky");
    expect(r).toContain("position: sticky");
    expect(r).toContain("top: var(--tabs-top, 0px)");
  });
  it("has an opaque backing, extended upward by ::before, so no content shows above or through it", () => {
    const r = rule(".tabs-sticky");
    expect(r).toContain("background: var(--color-surface-primary)");
    expect(r).not.toContain("gradient");
    expect(r).not.toContain("color-mix");
    const b = rule(".tabs-sticky::before");
    expect(b).toContain("height: var(--tabs-mask, 0px)");
    expect(b).toContain("background: var(--color-surface-primary)");
  });
});
