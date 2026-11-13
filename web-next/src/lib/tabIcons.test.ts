import { describe, expect, it } from "vitest";

import { TAB_GLYPH_MARKUP } from "@/components/tabGlyphMarkup.generated";
import { TAB_ICONS } from "./tabIcons";

describe("tab icon registry", () => {
  it("has SVG markup for every registered Ionicons glyph", () => {
    for (const [name, glyph] of Object.entries(TAB_ICONS)) {
      expect(TAB_GLYPH_MARKUP[glyph], `${name} -> ${glyph}`).toBeTruthy();
    }
  });
  it("only outline glyphs, so tabs read as one icon family", () => {
    for (const glyph of Object.values(TAB_ICONS)) expect(glyph.endsWith("-outline")).toBe(true);
  });
});
