import React from 'react';
import { Ionicons } from '@expo/vector-icons';

import { tabIconGlyph, type TabIconName } from '../lib/tabIcons';

/**
 * Tab glyph: the registry name (lib/tabIcons.ts, byte-identical with web)
 * resolves to the outline Ionicons glyph that web's TabGlyph draws as inline
 * SVG, so a tab is the same icon on both platforms.
 */
export default function TabIcon({ name, color, size = 18 }: { name: TabIconName; color: string; size?: number }) {
  return <Ionicons name={tabIconGlyph(name) as React.ComponentProps<typeof Ionicons>['name']} size={size} color={color} />;
}
