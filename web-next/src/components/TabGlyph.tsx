import { CUSTOM_TAB_GLYPHS, TAB_ICONS, type CustomGlyphElement, type TabIconName } from "@/lib/tabIcons";
import { TAB_GLYPH_MARKUP } from "./tabGlyphMarkup.generated";

/**
 * Tab glyph: the registry name (lib/tabIcons.ts) resolves to the same
 * outline Ionicons glyph mobile's TabIcon renders. Inline SVG from static,
 * build-time markup (tabGlyphMarkup.generated.ts), tinted by `currentColor`.
 */
/** Static SVG markup for a custom glyph registry entry (same shape as the generated Ionicons markup). */
export function customGlyphMarkup(elements: CustomGlyphElement[]): string {
  return elements
    .map((e) => {
      const attrs = Object.entries(e.attrs).map(([k, v]) => `${k}="${v}"`).join(" ");
      const paint = e.fill
        ? 'fill="currentColor"'
        : 'fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="32"';
      return `<${e.tag} ${attrs} ${paint}/>`;
    })
    .join("");
}

export function TabGlyph({ name, size = 18 }: { name: TabIconName; size?: number }) {
  const glyph = TAB_ICONS[name] as string;
  const custom = CUSTOM_TAB_GLYPHS[glyph];
  const markup = custom ? customGlyphMarkup(custom) : TAB_GLYPH_MARKUP[glyph];
  if (!markup) return null;
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 512 512"
      aria-hidden="true"
      focusable="false"
      fill="currentColor"
      style={{ display: "block", flexShrink: 0 }}
      dangerouslySetInnerHTML={{ __html: markup }}
    />
  );
}
