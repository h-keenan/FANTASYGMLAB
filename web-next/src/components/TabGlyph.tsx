import { CUSTOM_TAB_GLYPHS, TAB_ICONS, type CustomGlyphElement, type TabIconName } from "@/lib/tabIcons";
/** Static sprite of the Ionicons outline glyphs (public/tab-glyphs.svg), fetched once and cached instead of bundled as JS strings. */
export const TAB_GLYPH_SPRITE_URL = "/tab-glyphs.svg";

/**
 * Tab glyph: the registry name (lib/tabIcons.ts) resolves to the same
 * outline Ionicons glyph mobile's TabIcon renders. An inline <svg> that `<use>`s a
 * symbol from the static sprite (public/tab-glyphs.svg), tinted by `currentColor`
 * (a `<use>` shadow tree inherits the color of the <svg>, so it follows the label).
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
  const common = {
    width: size,
    height: size,
    viewBox: "0 0 512 512",
    "aria-hidden": true as const,
    focusable: "false" as const,
    fill: "currentColor",
    style: { display: "block", flexShrink: 0 } as const,
  };
  if (custom) return <svg {...common} dangerouslySetInnerHTML={{ __html: customGlyphMarkup(custom) }} />;
  if (!glyph) return null;
  return (
    <svg {...common}>
      <use href={`${TAB_GLYPH_SPRITE_URL}#${glyph}`} />
    </svg>
  );
}
