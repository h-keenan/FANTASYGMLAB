import React, { useEffect, useMemo, useState } from 'react';
import { View } from 'react-native';

import AccentCard from './AccentCard';
import { SimBadgeChips } from './SimAchievements';
import { simPlayerBadges } from '../lib/simAchievements';
import AppText from './AppText';
import ErrorState from './ErrorState';
import { Section as PqvSection } from './PlayerQuickViewSheet';
import { SkeletonCard } from './SkeletonBlock';
import { SimTeamIdentity, SimTeamLogo } from './SimTeamIdentity';
import { createSimStyles } from './SimGameParts';
import ToneBadge from './ToneBadge';
import { useThemeMode } from '../context/ThemeModeContext';
import { api } from '../lib/api';
import { simSeasonText, type SimPlayerHistoryResponse } from '../lib/simGame';
import { simDraftSlotText, simHistoryText, simWhenLabel } from '../lib/simHistory';

/**
 * A player's History tab in the Fantasy Sim quick view: where he came from (the round and pick he was drafted at),
 * every trade, claim and cut since, and a line per season with the team(s) he played for. Derived from the game's event
 * log (GET /players/{id}/history), fetched when the tab opens. Twin of web's SimPlayerHistory.
 */
export function SimPlayerHistory({ gameId, playerId }: { gameId: string; playerId: string }) {
  const { colors } = useThemeMode();
  const common = useMemo(() => createSimStyles(colors), [colors]);
  const [data, setData] = useState<SimPlayerHistoryResponse | null>(null);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    api.getSimPlayerHistory(gameId, playerId).then(
      (body) => {
        if (cancelled) return;
        if (body.reason) setFailed(true);
        else setData(body);
      },
      () => {
        if (!cancelled) setFailed(true);
      },
    );
    return () => {
      cancelled = true;
    };
  }, [gameId, playerId, attempt]);

  if (failed) {
    return (
      <ErrorState
        title="History did not load"
        message="Check your connection and try again."
        onRetry={() => {
          setFailed(false);
          setAttempt((n) => n + 1);
        }}
      />
    );
  }
  if (!data) return <SkeletonCard rows={3} />;
  const origin = data.origin;
  const entries = (data.entries ?? []).filter((e) => e !== origin && e.kind !== 'drafted' && e.kind !== 'started');
  const seasons = data.seasons ?? [];
  return (
    <View style={common.stack} testID="sim-player-history">
      <SimBadgeChips items={simPlayerBadges(data.achievements, playerId)} />
      <PqvSection title="Origin">
        {origin ? (
          <AccentCard accent={colors.accent} compact>
            <View style={common.row}>
              {origin.team_name ? <SimTeamLogo name={origin.team_name} size='row' /> : null}
              <View style={common.grow}>
                <AppText style={common.bodyStrong}>{origin.kind === 'drafted' ? simDraftSlotText(origin.round, origin.pick, origin.auto) : `Started on ${origin.team_name ?? 'a team'}`}</AppText>
                <AppText style={common.small}>{simHistoryText(origin)}</AppText>
              </View>
            </View>
            <ToneBadge label={simWhenLabel(origin)} color={colors.textSecondary} size="xs" />
          </AccentCard>
        ) : (
          <AppText style={common.small}>Not on a team when the game began.</AppText>
        )}
        <AppText style={common.small}>{data.current_team?.team_name ? `Now with ${data.current_team.team_name}.` : 'Free agent.'}</AppText>
      </PqvSection>

      <PqvSection title="Moves">
        {entries.length === 0 ? (
          <AppText style={common.small}>No moves yet: still where the draft put him.</AppText>
        ) : (
          <View style={common.stack}>
            {entries.map((e, i) => (
              <AccentCard key={i} accent={colors.borderStrong} compact>
                <View style={common.row}>
                  <ToneBadge label={simWhenLabel(e)} color={colors.textSecondary} size="xs" />
                  <ToneBadge label={e.kind} color={colors.premium} size="xs" />
                </View>
                <AppText style={common.body}>{simHistoryText(e)}</AppText>
              </AccentCard>
            ))}
          </View>
        )}
      </PqvSection>

      {seasons.length > 0 ? (
        <PqvSection title="Seasons with each team">
          <View style={common.stack}>
            {seasons.map((s) => (
              <AccentCard key={s.season} accent={colors.borderStrong} compact>
                <View style={common.rowBetween}>
                  <AppText style={common.bodyStrong}>{simSeasonText(s) || `Season ${s.season}`}</AppText>
                  <AppText style={common.muted}>
                    {s.games} games · {s.points.toFixed(1)} pts{s.ppg != null ? ` · ${s.ppg.toFixed(1)} ppg` : ''}
                  </AppText>
                </View>
                {s.teams.map((t) => (
                  <View key={t.team_id} style={common.rowBetween}>
                    <View style={[common.row, common.grow]}>{t.team_name ? <SimTeamIdentity name={t.team_name} size='inline' bold={false} fontSize={12} /> : null}</View>
                    <AppText style={common.muted}>
                      {t.games} g · {t.ppg.toFixed(1)} ppg
                    </AppText>
                  </View>
                ))}
              </AccentCard>
            ))}
          </View>
        </PqvSection>
      ) : null}
    </View>
  );
}
