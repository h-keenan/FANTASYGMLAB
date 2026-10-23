import React from 'react';

import ToneBadge from './ToneBadge';
import { useThemeMode } from '../context/ThemeModeContext';
import { resolvePlayerTier } from '../lib/playerTier';

/** Tier -> ToneBadge adapter: picks the tier's color and label, the shared pill draws it. */
export default function TierBadge({
  storedTier,
  size = 'sm',
}: {
  storedTier: string | null | undefined;
  size?: 'sm' | 'md';
}) {
  const { isDark } = useThemeMode();
  if (!storedTier) return null;
  const tier = resolvePlayerTier(storedTier, isDark);
  return (
    <ToneBadge
      label={size === 'md' ? tier.shortLabel : tier.abbrLabel}
      color={tier.color}
      size={size === 'md' ? 'sm' : 'xs'}
    />
  );
}
