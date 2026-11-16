import { renderToStaticMarkup } from "react-dom/server";
import { createElement } from "react";
import { describe, expect, it } from "vitest";

import { TabGlyph } from "@/components/TabGlyph";
import { TAB_GLYPH_MARKUP } from "@/components/tabGlyphMarkup.generated";
import { CUSTOM_TAB_GLYPHS, TAB_ICONS, isCustomTabGlyph } from "./tabIcons";

describe("tab icon registry", () => {
  it("has SVG markup for every registered Ionicons glyph", () => {
    for (const [name, glyph] of Object.entries(TAB_ICONS)) {
      expect(TAB_GLYPH_MARKUP[glyph] ?? CUSTOM_TAB_GLYPHS[glyph], `${name} -> ${glyph}`).toBeTruthy();
    }
  });
  it("only outline glyphs, so tabs read as one icon family", () => {
    for (const glyph of Object.values(TAB_ICONS).filter((g) => !isCustomTabGlyph(g))) expect(glyph.endsWith("-outline")).toBe(true);
  });
  it("renders the custom Fantasy Sim glyph", () => {
    const html = renderToStaticMarkup(createElement(TabGlyph, { name: "fantasySim" }));
    expect(html).toContain("M224 272l96 56-96 56z");
    expect(html).toContain("<rect");
  });
});
