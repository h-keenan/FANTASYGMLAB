import { Ionicons } from '@expo/vector-icons';

import type { DashboardItemCategory } from './api';
import type { ThemeColors } from '../theme';

/**
 * How a Next Move tile's `category` renders as an icon/label/color — one
 * shared mapping so every surface that shows a DashboardItem (Dashboard's
 * own Next Move feed, and the cross-league Portfolio screen's one-line
 * "top item" per league) agrees on what "watch" vs. "waiver_opportunity"
 * looks like, instead of each screen inventing its own. Extracted from
 * DashboardScreen.tsx, which was the sole owner before Portfolio needed the
 * exact same mapping.
 */
export function categoryMeta(
  colors: ThemeColors,
): Record<DashboardItemCategory, { label: string; icon: React.ComponentProps<typeof Ionicons>['name']; color: string }> {
  return {
    top_priority: { label: 'Top Priority', icon: 'flash', color: colors.accent },
    watch: { label: 'Watch', icon: 'eye-outline', color: colors.danger },
    waiver_opportunity: { label: 'Waiver Opportunity', icon: 'swap-horizontal-outline', color: colors.premium },
    league_movement: { label: 'League Movement', icon: 'trending-up-outline', color: colors.textSecondary },
  };
}
