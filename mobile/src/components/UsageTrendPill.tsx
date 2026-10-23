import React from 'react';

import ToneBadge from './ToneBadge';
import { useThemeMode } from '../context/ThemeModeContext';
import type { UsageTrend } from '../lib/api';

/**
 * Usage-trend -> ToneBadge adapter: arrow plus the signed move, no words.
 * The server only sends a usage_trend once the read clears its confidence
 * gate (modules/rankings.py: recency_trend_display).
 */
export default function UsageTrendPill({ trend }: { trend: UsageTrend }) {
  const { colors } = useThemeMode();
  const rising = trend.direction === 'up';
  return (
    <ToneBadge
      size="xs"
      icon={rising ? 'arrow-up' : 'arrow-down'}
      color={rising ? colors.success : colors.danger}
      label={`${trend.magnitude_pct}%`}
    />
  );
}
