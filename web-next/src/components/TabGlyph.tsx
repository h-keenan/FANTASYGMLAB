import { TAB_ICONS, type TabIconName } from "@/lib/tabIcons";
import { TAB_GLYPH_MARKUP } from "./tabGlyphMarkup.generated";

/**
 * Tab glyph: the registry name (lib/tabIcons.ts) resolves to the same
 * outline Ionicons glyph mobile's TabIcon renders. Inline SVG from static,
 * build-time markup (tabGlyphMarkup.generated.ts), tinted by `currentColor`.
 */
export function TabGlyph({ name, size = 18 }: { name: TabIconName; size?: number }) {
  const markup = TAB_GLYPH_MARKUP[TAB_ICONS[name]];
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
