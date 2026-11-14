import React, { useEffect, useMemo, useState } from 'react';
import { View } from 'react-native';

import AppText from './AppText';
import CompactModule from './CompactModule';
import ErrorState from './ErrorState';
import { Section as PqvSection } from './PlayerQuickViewSheet';
import { SkeletonCard } from './SkeletonBlock';
import { createSimStyles } from './SimGameParts';
import ToneBadge from './ToneBadge';
import { useThemeMode } from '../context/ThemeModeContext';
import { api } from '../lib/api';
import type { SimHistorySeason } from '../lib/simGame';
import { simCareerSeasonParts, simCareerSeasonTitle } from '../lib/simHistory';

/**
 * The sim's OWN seasons of a player, newest first, under the real career in the Stats tab: one compact module per season played
 * (collapsed: "S3 2028 · 14 g · 212.4 pts · 15.2 avg · WR12"; open: his game log and best week). Twin of web's SimSimSeasons; read from
 * the game's event log, so it covers every season played and saves made before this view existed. Points are what the engine stores.
 */
export function SimSimSeasons({ gameId, playerId }: { gameId: string; playerId: string }) {
  const { colors } = useThemeMode();
  const common = useMemo(() => createSimStyles(colors), [colors]);
  const [seasons, setSeasons] = useState<SimHistorySeason[] | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api.getSimPlayerHistory(gameId, playerId).then(
      (body) => {
        if (cancelled) return;
        if (body.reason) setFailed(true);
        else setSeasons([...(body.seasons ?? [])].sort((a, b) => b.season - a.season));
      },
      () => {
        if (!cancelled) setFailed(true);
      },
    );
    return () => {
      cancelled = true;
    };
  }, [gameId, playerId]);

  if (failed) return <ErrorState title="Sim seasons did not load" message="Check your connection and try again." />;
  if (seasons == null) return <SkeletonCard rows={2} />;
  return (
    <PqvSection title="Sim seasons">
      <View style={common.row}>
        <ToneBadge label="Sim" color={colors.accent} size="xs" />
      </View>
      {seasons.length === 0 ? (
        <AppText style={common.small}>No games played in this sim yet. His seasons appear here as the weeks are played.</AppText>
      ) : (
        seasons.map((s, index) => (
          <CompactModule key={s.season} id={`simstats.${playerId}.${s.season}`} title={simCareerSeasonTitle(s)} parts={simCareerSeasonParts(s)} defaultOpen={index === 0} persist={false}>
            <View style={common.stack}>
              {s.best_week ? (
                <AppText style={common.small}>
                  Best week Wk {s.best_week.week} ({s.best_week.points.toFixed(1)})
                  {s.teams.length ? ` · ${s.teams.map((t) => t.team_name).filter(Boolean).join(', ')}` : ''}
                </AppText>
              ) : null}
              {(s.weeks ?? []).map((w) => (
                <View key={`${w.week}-${w.playoff ? 'p' : 'r'}`} style={common.rowBetween}>
                  <AppText style={common.muted}>{w.playoff ? `Playoffs ${w.week}` : `Wk ${w.week}`}</AppText>
                  <AppText style={common.bodyStrong}>{w.points.toFixed(1)}</AppText>
                </View>
              ))}
            </View>
          </CompactModule>
        ))
      )}
    </PqvSection>
  );
}
