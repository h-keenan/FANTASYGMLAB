import React from 'react';
import { Ionicons } from '@expo/vector-icons';

import type { SimGlyphName } from '../lib/simGame';

type IconName = React.ComponentProps<typeof Ionicons>['name'];

/** The glyph per game section/status (mirrors web-next's SimGlyph, which draws the same names as inline SVG). */
export const SIM_GLYPH_ICONS: Record<SimGlyphName, IconName> = {
  matchup: 'flash',
  checklist: 'checkbox-outline',
  waiver: 'add-circle-outline',
  bye: 'calendar-outline',
  injury: 'medkit-outline',
  trade: 'swap-horizontal',
  standings: 'podium-outline',
  hot: 'flame',
  cold: 'snow-outline',
  league: 'globe-outline',
  team: 'shield-outline',
  check: 'checkmark',
  alert: 'warning-outline',
  spark: 'sparkles',
  trophy: 'trophy-outline',
};

export default function SimGlyph({ name, color, size = 16 }: { name: SimGlyphName; color: string; size?: number }) {
  return <Ionicons name={SIM_GLYPH_ICONS[name]} size={size} color={color} />;
}
