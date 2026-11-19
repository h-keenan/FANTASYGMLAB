import { readFileSync } from "node:fs";
import path from "node:path";
import { renderToStaticMarkup } from "react-dom/server";
import { createElement } from "react";
import { describe, expect, it } from "vitest";

import { TAB_GLYPH_SPRITE_URL, TabGlyph } from "@/components/TabGlyph";
import { CUSTOM_TAB_GLYPHS, TAB_ICONS, isCustomTabGlyph } from "./tabIcons";

const SPRITE = readFileSync(path.join(process.cwd(), "public", TAB_GLYPH_SPRITE_URL), "utf8");
const spriteIds = new Set([...SPRITE.matchAll(/<symbol id="([^"]+)"/g)].map((m) => m[1]));

describe("tab icon registry", () => {
  it("has SVG markup for every registered Ionicons glyph", () => {
    for (const [name, glyph] of Object.entries(TAB_ICONS)) {
      expect(spriteIds.has(glyph) || glyph in CUSTOM_TAB_GLYPHS, `${name} -> ${glyph}`).toBe(true);
    }
  });
  it("only outline glyphs, so tabs read as one icon family", () => {
    for (const glyph of Object.values(TAB_ICONS).filter((g) => !isCustomTabGlyph(g))) expect(glyph.endsWith("-outline")).toBe(true);
  });
  it("draws an Ionicons glyph through the sprite so currentColor still tints it", () => {
    const html = renderToStaticMarkup(createElement(TabGlyph, { name: "home" as never }));
    expect(html).toContain('fill="currentColor"');
    expect(html).toContain(`href="${TAB_GLYPH_SPRITE_URL}#home-outline"`);
  });
  it("renders the custom Fantasy Sim glyph", () => {
    const html = renderToStaticMarkup(createElement(TabGlyph, { name: "fantasySim" }));
    expect(html).toContain("M224 272l96 56-96 56z");
    expect(html).toContain("<rect");
  });
});
