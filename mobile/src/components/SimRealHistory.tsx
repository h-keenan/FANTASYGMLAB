import React, { useEffect, useMemo, useState } from 'react';
import { Pressable, View } from 'react-native';

import AppText from './AppText';
import ErrorState from './ErrorState';
import { Section as PqvSection } from './PlayerQuickViewSheet';
import { createSimStyles } from './SimGameParts';
import { useThemeMode } from '../context/ThemeModeContext';
import { api, type CareerSeason, type WeeklyStatPoint } from '../lib/api';
import { simCareerAsOf, simGameLog } from '../lib/simAsOf';

/**
 * The real-NFL record behind a Fantasy Sim player, cut to the last finished real season at the sim's start (lib/simAsOf.ts):
 * career season by season and that season's game log. Nothing from the season in progress, no news. Twin of web's SimRealHistory;
 * fills the Stats tab the as-of cut would otherwise leave empty.
 */
export function SimRealHistory({ playerId, asOf }: { playerId: string; asOf: number }) {
  const { colors } = useThemeMode();
  const common = useMemo(() => createSimStyles(colors), [colors]);
  const [career, setCareer] = useState<CareerSeason[] | null>(null);
  const [log, setLog] = useState<WeeklyStatPoint[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [open, setOpen] = useState(0);

  useEffect(() => {
    let cancelled = false;
    api.getPlayerCareer(playerId).then(
      (body) => {
        if (!cancelled) setCareer(simCareerAsOf(body.seasons, asOf));
      },
      () => {
        if (!cancelled) setFailed(true);
      },
    );
    api.getPlayerWeeklyStats(playerId, asOf).then(
      (body) => {
        if (!cancelled) setLog(body.weeks);
      },
      () => {
        if (!cancelled) setLog([]);
      },
    );
    return () => {
      cancelled = true;
    };
  }, [playerId, asOf]);

  if (failed) return <ErrorState title="Past seasons did not load" message="Check your connection and try again." />;
  if (career == null) return <AppText style={common.small}>Loading past seasons…</AppText>;
  const summary = simGameLog(log ?? []);
  if (career.length === 0 && summary.games === 0) return <AppText style={common.small}>No NFL seasons on file before this one.</AppText>;
  return (
    <View style={common.stack} testID="sim-real-history">
      {career.length > 0 ? (
        <PqvSection title={`Career by season · through ${asOf}`}>
          {career.map((season, index) => (
            <View key={season.season}>
              <Pressable accessibilityRole="button" accessibilityState={{ expanded: open === index }} onPress={() => setOpen(open === index ? -1 : index)} style={common.rowBetween}>
                <AppText style={common.bodyStrong}>
                  {season.season}
                  {season.games != null ? ` · ${season.games} games` : ''}
                  {season.age != null ? ` · Age ${season.age}` : ''}
                </AppText>
                <AppText style={common.muted}>{open === index ? '▲' : '▼'}</AppText>
              </Pressable>
              {open === index
                ? season.key_stats.length > 0
                  ? season.key_stats.map((item) => (
                      <View key={item.label} style={common.rowBetween}>
                        <AppText style={common.small}>{item.label}</AppText>
                        <AppText style={common.bodyStrong}>{item.value}</AppText>
                      </View>
                    ))
                  : <AppText style={common.small}>No stats recorded for this season.</AppText>
                : null}
            </View>
          ))}
        </PqvSection>
      ) : null}
      {summary.games > 0 ? (
        <PqvSection title={`Game log · ${asOf}`}>
          <AppText style={common.small}>
            {summary.games} games · {summary.total.toFixed(1)} pts{summary.avg != null ? ` · ${summary.avg.toFixed(1)} avg` : ''}
            {summary.best ? ` · best Wk ${summary.best.week} (${(summary.best.fantasy_points_ppr ?? 0).toFixed(1)})` : ''}
          </AppText>
          {summary.weeks.map((w) => (
            <View key={w.week} style={common.rowBetween}>
              <AppText style={common.muted}>Wk {w.week}</AppText>
              <AppText style={common.bodyStrong}>{(w.fantasy_points_ppr ?? 0).toFixed(1)}</AppText>
            </View>
          ))}
        </PqvSection>
      ) : null}
    </View>
  );
}
