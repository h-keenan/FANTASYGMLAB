import React from 'react';
import { Ionicons } from '@expo/vector-icons';
import Svg, { Circle, Path, Rect } from 'react-native-svg';

import { CUSTOM_TAB_GLYPHS, TAB_ICONS, tabIconGlyph, type TabIconName } from '../lib/tabIcons';

/**
 * Tab glyph: the registry name (lib/tabIcons.ts, byte-identical with web)
 * resolves to the outline Ionicons glyph that web's TabGlyph draws as inline
 * SVG, so a tab is the same icon on both platforms. Custom (non-Ionicons)
 * registry entries are drawn with react-native-svg from the same element specs.
 */
export default function TabIcon({ name, color, size = 18 }: { name: TabIconName; color: string; size?: number }) {
  const custom = CUSTOM_TAB_GLYPHS[TAB_ICONS[name] as string];
  if (custom) {
    const stroke = { stroke: color, strokeWidth: 32, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const, fill: 'none' };
    return (
      <Svg width={size} height={size} viewBox="0 0 512 512">
        {custom.map((e, i) => {
          const paint = e.fill ? { fill: color } : stroke;
          const attrs = e.attrs as any;
          if (e.tag === 'rect') return <Rect key={i} {...attrs} {...paint} />;
          if (e.tag === 'circle') return <Circle key={i} {...attrs} {...paint} />;
          return <Path key={i} {...attrs} {...paint} />;
        })}
      </Svg>
    );
  }
  return <Ionicons name={tabIconGlyph(name) as React.ComponentProps<typeof Ionicons>['name']} size={size} color={color} />;
}
