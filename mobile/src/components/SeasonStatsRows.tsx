import React from 'react';
import { View } from 'react-native';

import { useThemeMode } from '../context/ThemeModeContext';

import AppText from './AppText';
import { StatRowsCard, type ExploreHandler } from './StatRows';
import type { QuickViewStats, UsageProfile } from '../lib/api';
import { seasonStatGroups } from '../lib/playerQuickViewPresentation';
import { poolCaption, statItemRows, usageCardCoversLegacyTiles } from '../lib/statRows';

/** Season stats as percentile-row cards (Production / Fantasy / Efficiency),
 * shared by the quick view sheet and the player detail Stats tab. The legacy
 * season "Usage" tiles are dropped when the unified Usage card is shown. */
export default function SeasonStatsRows({
  stats,
  usageProfile,
  onExplore,
  headlineLabels = ['PPR PPG'],
}: {
  stats: QuickViewStats | null;
  usageProfile: UsageProfile | null | undefined;
  onExplore?: ExploreHandler;
  headlineLabels?: string[];
}) {
  const { colors } = useThemeMode();
  if (!stats) return null;
  const hideLegacyUsage = usageCardCoversLegacyTiles(usageProfile);
  return (
    <>
      {stats.seasons.map((season) => (
        <View key={season.label}>
          <AppText style={{ fontSize: 15, fontWeight: '700', marginVertical: 8, color: colors.textPrimary }}>
            {season.label}
            {season.games != null ? ` · ${season.games} games` : ''}
          </AppText>
          {seasonStatGroups(season)
            .filter((group) => !(hideLegacyUsage && group.title === 'Usage'))
            .map((group) => {
              const caption = poolCaption(stats.position, season.season);
              return (
                <StatRowsCard
                  key={group.title}
                  title={group.title}
                  caption={caption ? `Percentile ${caption}` : null}
                  rows={statItemRows(group.items, stats.position, season.season).filter((row) => !headlineLabels.includes(row.label))}
                  onExplore={onExplore}
                  collapseAfter={3}
                />
              );
            })}
        </View>
      ))}
    </>
  );
}
