import React from 'react';
import { Ionicons } from '@expo/vector-icons';

import type { OffseasonIcon } from '../lib/simOffseasonSummary';

/** Section-header and stepper glyphs for the Fantasy Sim offseason (twin of web-next OffseasonGlyph.tsx). */
export const OFFSEASON_IONICON: Record<OffseasonIcon, keyof typeof Ionicons.glyphMap> = {
  review: 'document-text-outline',
  draft: 'time-outline',
  roster: 'people-outline',
  season: 'trophy-outline',
  retire: 'home-outline',
  aging: 'trending-up-outline',
  picks: 'ticket-outline',
  log: 'list-outline',
  reserve: 'medkit-outline',
  trade: 'swap-horizontal',
  team: 'shirt-outline',
};

export function OffseasonGlyph({ name, size = 16, color }: { name: OffseasonIcon; size?: number; color: string }) {
  return <Ionicons name={OFFSEASON_IONICON[name]} size={size} color={color} />;
}
